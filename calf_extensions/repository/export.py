"""Export an already collected project portal. No Git or source repository reads."""
import copy
import json
from pathlib import Path
from .capture import Store
from .model import RepositoryError,SOURCE_LIMIT,TOTAL_SOURCE_LIMIT,canonical,classify,digest,validate_navigation
from .viewer import html


def export_capture(data_dir,capture_id,destination,include_source=False):
    store=Store(data_dir);capture=store.load(capture_id)
    path=store.directory/'navigation'/(capture_id+'.json')
    if not path.is_file():raise RepositoryError('NAVIGATION_MISSING','No project map was collected for this capture')
    if path.stat().st_size>32*1024*1024:raise RepositoryError('EXPORT_LIMIT','Project map exceeds export bound',3)
    payload=json.loads(path.read_bytes());validate_navigation(payload['graph'])
    if payload['graph']['capture_id']!=capture_id or payload['capture']['capture_id']!=capture_id:raise RepositoryError('CAPTURE_MISMATCH','Project map belongs to another capture')
    payload=copy.deepcopy(payload)
    for key in ['root','git_dir','common_dir']:payload['capture']['repository'].pop(key,None)
    sources={};comparisons={};included=0;excluded=0
    for path_id,meta in payload['graph']['source_captures'].items():
        sha=meta.get('sha256');cached=store.directory/'sources'/sha if sha else None
        if not include_source or not cached or not cached.is_file() or cached.stat().st_size>SOURCE_LIMIT or included+cached.stat().st_size>TOTAL_SOURCE_LIMIT:
            excluded+=1;continue
        raw=cached.read_bytes()
        if digest(raw)!=sha:raise RepositoryError('SOURCE_CACHE_CHANGED','Captured source changed')
        value=dict(meta,**{'text':classify(raw).get('text'),'version':'captured','path_id':path_id});sources[path_id+':captured']=value;included+=len(raw)
        for version in ['head','index','working']:
            key=digest(canonical([capture_id,path_id,'head',version]));candidate=store.directory/'comparisons'/(key+'.json')
            if not candidate.is_file() or candidate.stat().st_size>8*1024*1024:continue
            value=json.loads(candidate.read_bytes())
            # Comparisons are cached products of exact sources, never refreshed on export.
            for side in ['left','right']:
                value[side].pop('snapshot_path',None);value[side].pop('current_path',None)
            comparisons[path_id+':'+version]=value
        key=digest(canonical([capture_id,path_id,'head','captured']));candidate=store.directory/'comparisons'/(key+'.json')
        if candidate.is_file() and candidate.stat().st_size<=8*1024*1024:
            value=json.loads(candidate.read_bytes())
            for side in ['left','right']:value[side].pop('snapshot_path',None);value[side].pop('current_path',None)
            comparisons[path_id+':captured']=value
    payload['export']={'source_included':include_source,'included_source_bytes':included,'source_entries':len(sources),'source_entries_excluded':excluded,'comparison_entries':len(comparisons),'absolute_editor_paths':False}
    output=Path(destination).expanduser().resolve()
    for protected in [Path(capture['repository'][key]) for key in ['root','git_dir','common_dir']]:
        if output==protected or output.is_relative_to(protected):raise RepositoryError('OUTPUT_IN_REPOSITORY','Export must stay outside the repository')
    if output==store.directory or output.is_relative_to(store.directory):raise RepositoryError('OUTPUT_IN_DATA','Use a new export directory outside app data')
    page=html({'mode':'offline','payload':payload,'sources':sources,'comparisons':comparisons})
    output.mkdir(parents=True,exist_ok=False)
    (output/'START_HERE.html').write_text(page,encoding='utf-8')
    (output/'project-navigation.json').write_bytes(canonical(payload))
    manifest={'capture_id':capture_id,'files':{name:digest((output/name).read_bytes()) for name in ['START_HERE.html','project-navigation.json']},'coverage':payload['export']}
    (output/'MANIFEST.json').write_bytes(canonical(manifest))
    return {'state':'COMPLETE','output':str(output),'manifest':manifest}
