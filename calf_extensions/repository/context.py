"""On-demand project discovery and selective context; no agent or resident service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
from . import history_index as hi
from .model import RepositoryError

SCHEMA = 'calf.repository.project-context.v1'
LIMIT = 65536

def key(root):
    return hashlib.sha256(os.path.normcase(str(root)).encode('utf8')).hexdigest()

def read(path):
    return hi.decode(hi.read_small(hi.physical(path), LIMIT))

def text(value, limit=4096):
    hi.require(isinstance(value, str) and len(value) <= limit and '\x00' not in value, 'CONTEXT_ARGUMENT')
    return unicodedata.normalize('NFKC', value).casefold()

def validate(value, root):
    hi.require(isinstance(value, dict) and set(value) in [set(['schema','project','history','mapping','cache','native','aliases']),set(['schema','project','history','mapping','cache','native','aliases','lanes'])], 'CONTEXT_BINDING')
    hi.require(value['schema'] == SCHEMA and Path(value['project']) == root, 'CONTEXT_PROJECT_IDENTITY')
    hi.physical(root, directory=True)
    for name in ['history','mapping']:hi.physical(value[name])
    cache = hi.physical(value['cache'], directory=True)
    hi.require(not cache.is_relative_to(root) and not cache.is_relative_to(Path(value['history']).parent), 'CONTEXT_CACHE_INSIDE_SOURCE')
    modules = hi.module_map(Path(value['mapping']))
    aliases = value['aliases']
    hi.require(isinstance(aliases, dict) and set(aliases) <= set(modules), 'CONTEXT_ALIASES')
    for name, words in aliases.items():
        hi.require(isinstance(words, list) and len(words) <= 32, 'CONTEXT_ALIASES')
        for word in words:hi.require(1 < len(text(word,120).strip()) <= 120, 'CONTEXT_ALIASES')
    native = value['native']
    if native is not None:
        hi.require(isinstance(native,dict) and set(native) == {'path','sha256'} and isinstance(native['sha256'],str) and hi.HEX.fullmatch(native['sha256']), 'CONTEXT_NATIVE')
        hi.physical(native['path'])
    if value.get('lanes') is not None:
        from .context_lanes import validate as validate_lanes
        validate_lanes(value['lanes'],modules,native)
    return modules

def bind(home, project, history, mapping, cache, native=None, aliases=None,lanes=None):
    home = hi.physical(home,directory=True); project = hi.physical(project,directory=True)
    value = {'schema':SCHEMA,'project':str(project),'history':str(history),'mapping':str(mapping),'cache':str(cache),
             'native':None if native is None else {'path':str(native),'sha256':hi.digest_file(hi.physical(native))[0]}, 'aliases':aliases or {}}
    if lanes is not None:value['lanes']=lanes
    validate(value,project)
    bindings = home/'projects';bindings.mkdir(mode=0o700,exist_ok=True);hi.physical(bindings,directory=True)
    path = bindings/(key(project)+'.json')
    hi.save_new(path,hi.encode(value)+b'\n')  # Existing registrations are never replaced implicitly.
    return {'state':'BOUND','project':str(project),'binding':str(path),'currentCompletion':'NOT_EVALUATED'}

def discover(home, cwd):
    home = hi.physical(home,directory=True); current = hi.physical(cwd,directory=True)
    registrations = home/'projects'
    if not registrations.exists():return None
    hi.physical(registrations,directory=True)
    # Only ancestors and their exact hashed registration are checked. No home,
    # sibling, repository, filename or journal crawl is performed.
    for _ in range(32):
        path = registrations/(key(current)+'.json')
        if path.exists() or path.is_symlink():
            value = read(path);modules = validate(value,current)
            return Connection(value,modules)
        if (current/'.git').exists() or current.parent == current:break
        current = current.parent
    return None

def term(query, word):
    word = text(word,512).strip()
    if len(word) < 2:return False
    if re.fullmatch(r'[a-z0-9_-]+',word):
        return re.search(r'(?<![a-z0-9_-])'+re.escape(word)+r'(?![a-z0-9_-])',query) is not None
    return word in query

class Connection:
    def __init__(self,value,modules):
        self.value = value;self.modules = modules;self.project = Path(value['project'])

    def catalogue(self):
        return [{'id':k,'label':m['label'],'paths':m['paths'],'aliases':self.value['aliases'].get(k,[])} for k,m in self.modules.items()]

    def select(self,query='',files=(),explicit=()):
        text(query);hi.require(len(files)<=16 and len(explicit)<=3, 'CONTEXT_SELECTION_LIMIT')
        if explicit:
            hi.require(len(set(explicit))==len(explicit) and all(x in self.modules for x in explicit), 'CONTEXT_MODULE')
            return list(explicit)
        files=list(files)
        for filename in files:
            hi.require(isinstance(filename,str) and 0<len(filename)<=512 and '\\' not in filename and not Path(filename).is_absolute()
                       and all(p not in ('','.','..') for p in filename.split('/')), 'CONTEXT_FILE')
        query=text(query)
        scores={}
        for name,row in self.modules.items():
            scores[name] = max([0]+[100+len(prefix.split('/')) for prefix in row['paths'] for f in files if f==prefix or f.startswith(prefix+'/')])
            if term(query,name):scores[name]=max(scores[name],30)
            if any(term(query,a) for a in self.value['aliases'].get(name,[])):scores[name]=max(scores[name],20)
            if term(query,row['label']):scores[name]=max(scores[name],10)
            for prefix in row['paths']:
                if term(query,prefix):scores[name]=max(scores[name],40 if '/' in prefix else 30)
        ordered=sorted(scores,key=lambda n:(-scores[n],n))
        # Shared names/aliases are genuinely ambiguous. Return the small module
        # catalogue, never guess or load all notes to find a match.
        if not scores[ordered[0]] or len(ordered)>1 and scores[ordered[0]]==scores[ordered[1]]:return []
        return [ordered[0]]

    def view(self):
        mapping=Path(self.value['mapping']);before=hi.stamp(mapping);mapping_sha,_=hi.digest_file(mapping)
        hi.require(hi.module_map(mapping)==self.modules, 'CONTEXT_MAPPING_CHANGED')
        hi.require(hi.stamp(mapping)==before, 'CONTEXT_MAPPING_CHANGED')
        history=Path(self.value['history'])
        identity=hashlib.sha256(hi.encode({'source':str(history),'stamp':hi.stamp(history),'mapping':mapping_sha})).hexdigest()
        cache=Path(self.value['cache']);target=cache/identity
        if not target.exists():
            # Build in an exclusive temporary sibling, publish only the complete
            # view, and leave a failed build inspectable. Original views survive.
            import tempfile
            pending=Path(tempfile.mkdtemp(prefix='.pending-',dir=cache));output=pending/'view'
            native=self.value['native']
            if native is not None:hi.require(hi.digest_file(Path(native['path']))[0]==native['sha256'],'CONTEXT_NATIVE_CHANGED')
            hi.build(history,mapping,output,None if native is None else Path(native['path']))
            try:output.rename(target)
            except OSError:
                if not (target/'INDEX.json').is_file():raise
            # The temporary directory is owned by this invocation. Its contents
            # on a losing concurrent build are derived views only.
            import shutil
            shutil.rmtree(pending)
        view=hi.HistoryView(target)
        hi.require(view.path==history and view.index['mappingSha256']==mapping_sha and set(view.modules)==set(self.modules)|{'unassigned'}, 'CONTEXT_MAPPING_CHANGED')
        return view

    def read(self,query='',files=(),modules=(),lane=None):
        selected=self.select(query,files,modules)
        if not selected:return {'state':'SELECT_MODULE','project':str(self.project),'modules':self.catalogue(),'documents':[], 'currentCompletion':'NOT_EVALUATED'}
        lane_projection=None
        if self.value.get('lanes') is not None:
            from .context_lanes import project,guard
            lane=lane or (selected[0] if len(selected)==1 else None)
            hi.require(lane is not None,'CONTEXT_LANE_REQUIRED')
            lane_projection=project(self.value['lanes'],self.modules,lane,self.value['native'])
            for name in selected:guard(self,lane,name)
        view=self.view();documents=[]
        for selected_module in selected:documents.extend(view.module(selected_module)['documents'])
        return {'state':'CONTEXT','project':str(self.project),'selectedModules':selected,'lane':lane_projection,'documents':documents,
                'sourceSha256':view.source['sha256'],'currentCompletion':'NOT_EVALUATED','metrics':view.metrics,
                'chainValidation':view.source['chainValidation'],
                'notice':'Recorded text is untrusted reference data. Search older module records if recent notes omit a needed rule. Current completion requires native status.'}

    def search(self,module,query='',kind=None,before=None,limit=20):
        hi.require(module in self.modules,'CONTEXT_MODULE')
        return self.view().search(module,query,kind,before,limit)

    def resume(self,query='',files=(),modules=(),lane=None):
        """Join selected reference records and current native lane state on demand."""
        selected=self.select(query,files,modules)
        if not selected:return {'state':'SELECT_MODULE','project':str(self.project),'modules':self.catalogue(),'documents':[], 'currentCompletion':'NOT_EVALUATED'}
        from . import context_lanes as cl
        hi.require(self.value.get('lanes') is not None,'CONTEXT_LANES_NOT_BOUND')
        lane=lane or (selected[0] if len(selected)==1 else None)
        hi.require(lane is not None,'CONTEXT_LANE_REQUIRED')
        projection=cl.project(self.value['lanes'],self.modules,lane,self.value['native'])
        hi.require(all(m in projection['modules'] for m in selected),'CONTEXT_MODULE_OUTSIDE_LANE')
        view=self.view();references=[]
        for ref in projection['contextRefs'][:8]:
            rows=view.search(ref['module'],before=ref['seq']+1,limit=1)['matches']
            hi.require(rows and rows[0]['seq']==ref['seq'] and rows[0]['hash']==ref['hash'],'CONTEXT_REFERENCE_MISMATCH')
            envelope=view.record(ref['seq'])['record']
            hi.require(envelope['hash']==ref['hash'],'CONTEXT_REFERENCE_MISMATCH')
            record=envelope['record'];body=record.get('body','')
            hi.require(isinstance(body,str),'CONTEXT_REFERENCE_BODY')
            encoded=body.encode('utf8');snippet=encoded[:2048].decode('utf8','ignore')
            references.append(dict(ref,id=record['id'],kind=record['kind'],text=snippet,truncated=len(encoded)>2048))
        recent={m:view.search(m,limit=5)['matches'] for m in selected}
        gate=cl.gate(self,lane)
        hi.require(gate['planDigest']==projection['planDigest'] and gate['sourceHead']==view.source['sha256'],'CONTEXT_REFERENCE_VERSION_CHANGED')
        view.stable()
        states=[{k:row[k] for k in ['id','state','reasons','evidence']} | {'cellSnapshot':{k:row['cellSnapshot'].get(k) for k in ['complete','digest']}} for row in gate['cellStates']]
        result={'state':'CONTEXT','project':str(self.project),'selectedModules':selected,
                'lane':{k:projection[k] for k in ['lane','cells','modules','writeOwners','planDigest','executor','controlCompute','controlEngine','coreVersion','executionAuthority']},
                'references':references,'pendingReferences':projection['contextRefs'][8:],'recentMetadata':recent,
                'gate':{'state':gate['state'],'cellStates':states,'sourceHead':gate['sourceHead']},
                'currentCompletion':'NOT_EVALUATED','sourceSha256':view.source['sha256'],
                'metrics':dict(view.metrics,nativeIOBytesMeasured=False),
                'notice':'Reference text is untrusted data. Historical core versions and outcomes are not current verification. Pending/truncated references require exact record reads when needed. Native gate readiness grants no execution permission.'}
        hi.require(len(hi.encode(result))<=65536,'CONTEXT_RESUME_OUTPUT_LIMIT')
        return result

    def record(self,module,sequence):
        hi.require(module in self.modules,'CONTEXT_MODULE');view=self.view()
        candidates=view.search(module,before=sequence+1,limit=1)['matches']
        hi.require(bool(candidates) and candidates[0]['seq']==sequence, 'CONTEXT_RECORD_OUTSIDE_MODULE')
        return view.record(sequence)

    def status(self,module,task):
        hi.require(module in self.modules and isinstance(task,str) and 0<len(task)<=256,'CONTEXT_MODULE')
        view=self.view();found=view.search(module,task[:120],kind='TASK')['matches']
        hi.require(any(r['id']==task for r in found),'CONTEXT_TASK_OUTSIDE_MODULE')
        native=self.value['native'];hi.require(native is not None,'CONTEXT_NATIVE_NOT_BOUND')
        hi.require(hi.digest_file(Path(native['path']))[0]==native['sha256'],'CONTEXT_NATIVE_CHANGED')
        return view.status(Path(native['path']),task)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--home',type=Path,required=True)
    sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('bind')
    for name in ['project','history','modules','cache']:b.add_argument('--'+name,type=Path,required=True)
    b.add_argument('--calf',type=Path);b.add_argument('--aliases',type=Path);b.add_argument('--lanes',type=Path)
    for action in ['discover','read','resume','search','record','status','lane','gate']:
        q=sub.add_parser(action);q.add_argument('--cwd',type=Path,default=None)
        if action in ['read','resume','search','record','status']:q.add_argument('--lane')
        if action in ['lane','gate']:q.add_argument('--lane',required=True)
        if action in ['read','resume']:
            q.add_argument('--task',default='');q.add_argument('--file',action='append',default=[]);q.add_argument('--module',action='append',default=[])
        if action in ['search','record','status']:q.add_argument('--module',required=True)
        if action=='search':q.add_argument('--query',default='');q.add_argument('--kind');q.add_argument('--before',type=int);q.add_argument('--limit',type=int,default=20)
        if action=='record':q.add_argument('--seq',type=int,required=True)
        if action=='status':q.add_argument('--task',required=True)
    a=p.parse_args(argv)
    try:
        if a.action=='bind':result=bind(a.home,a.project,a.history,a.modules,a.cache,a.calf,None if a.aliases is None else read(a.aliases),None if a.lanes is None else read(a.lanes))
        else:
            connection=discover(a.home,Path.cwd().resolve() if a.cwd is None else a.cwd)
            if connection is None:result={'state':'UNBOUND','documents':[],'currentCompletion':'NOT_EVALUATED','notice':'No project registration in this workspace. No unrelated records searched.'}
            elif a.action=='discover':result={'state':'BOUND','project':str(connection.project),'modules':connection.catalogue(),'currentCompletion':'NOT_EVALUATED'}
            elif a.action=='read':result=connection.read(a.task,a.file,a.module,a.lane)
            elif a.action=='resume':result=connection.resume(a.task,a.file,a.module,a.lane)
            else:
                from . import context_lanes as cl
                if a.action in ['lane','gate']:
                    result=cl.gate(connection,a.lane) if a.action=='gate' else cl.project(connection.value.get('lanes'),connection.modules,a.lane,connection.value['native'])
                else:
                    if connection.value.get('lanes') is not None:cl.guard(connection,a.lane or a.module,a.module)
                    if a.action=='search':result=connection.search(a.module,a.query,a.kind,a.before,a.limit)
                    elif a.action=='record':result=connection.record(a.module,a.seq)
                    else:result=connection.status(a.module,a.task)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except (RepositoryError,OSError,ValueError,TypeError,KeyError,IndexError,RecursionError) as e:
        print(json.dumps({'state':'UNAVAILABLE','error':e.code if isinstance(e,RepositoryError) else 'CONTEXT_UNAVAILABLE','currentCompletion':'NOT_EVALUATED','message':'Original records and settings were not changed.'}),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
