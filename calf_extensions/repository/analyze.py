"""Project structure and Python AST references; no imports or execution of source."""
import ast
import json
import posixpath
import re
import time
from urllib.parse import unquote, urlsplit
from pathlib import PurePosixPath
from .compare import source
from .model import RepositoryError, digest, now, path_record, validate_navigation, validate_settings

ANALYZER='python-ast-v1'


def module_name(path):
    name=path[:-3].replace('/','.')
    return name[:-9] if name.endswith('.__init__') else '' if name=='__init__' else name


def local_bindings(node):
    names=set()
    def visit(value):
        if isinstance(value,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)) and value is not node:
            if hasattr(value,'name'):names.add(value.name)
            return
        if isinstance(value,ast.Name) and isinstance(value.ctx,(ast.Store,ast.Del)):names.add(value.id)
        if isinstance(value,(ast.Import,ast.ImportFrom)):
            names.update(a.asname or a.name.split('.')[0] for a in value.names)
        for child in ast.iter_child_nodes(value):visit(child)
    visit(node)
    if hasattr(node,'args'):
        names.update(a.arg for a in [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs])
        if node.args.vararg:names.add(node.args.vararg.arg)
        if node.args.kwarg:names.add(node.args.kwarg.arg)
    return names


def analyze(reader,store,capture,settings=None):
    settings=validate_settings({} if settings is None else settings);nodes={};edges=[];unresolved=[];files={};symbols={};module_files={};cache={};source_lines={};deadline=time.monotonic()+120
    def check():
        if reader.cancel_event.is_set():raise RepositoryError('CANCELLED','Analysis cancelled',130)
        if time.monotonic()>deadline:raise RepositoryError('ANALYSIS_TIMEOUT','Analysis exceeded its time budget')
    def segment(file,node):
        lines=source_lines.get(file['id'],[])
        if not lines or not getattr(node,'lineno',None):return ''
        start=node.lineno-1;end=getattr(node,'end_lineno',node.lineno)-1
        raw=lines[start][node.col_offset:getattr(node,'end_col_offset',len(lines[start]))] if start==end else lines[start][node.col_offset:]+b''.join(lines[start+1:min(end,start+4)])
        return raw[:256].decode('utf-8',errors='ignore')+('…' if len(raw)>256 or end>start+3 else '')
    def add_node(value):
        check()
        if len(nodes)>=50000:raise RepositoryError('ANALYSIS_LIMIT','Project entity limit exceeded',3)
        if value['id'] in nodes:raise RepositoryError('DUPLICATE_NODE','Duplicate graph entity')
        nodes[value['id']]=value
    def evidence(file,node=None):
        value=cache.get(file['id'],{})
        return {'file_id':'file:'+file['id'],'path':file['path'],'start_line':getattr(node,'lineno',1),'end_line':getattr(node,'end_lineno',getattr(node,'lineno',1)),
                'sha256':value.get('sha256'),'capture_id':capture['capture_id'],'method':ANALYZER if node else 'TRACKED_INVENTORY'}
    def edge(a,b,kind,ref,label=None):
        if len(edges)>=100000:raise RepositoryError('ANALYSIS_LIMIT','Project relation limit exceeded',3)
        if a not in nodes or b not in nodes:raise RepositoryError('EDGE_ENDPOINT','Missing graph endpoint')
        key=digest(json.dumps([a,b,kind,ref,label],sort_keys=True).encode())
        edges.append({'id':key,'from':a,'to':b,'kind':kind,'provenance':ref,'label':(label or kind)[:256]})
    root='project:'+capture['repository']['repository_id'];add_node({'id':root,'kind':'project','label':settings.get('label') or PurePosixPath(capture['repository']['root']).name,'description':settings.get('description',''),'state':'REGISTERED'})
    directories={'':root}
    for f in capture['files']:
        path=f['path'];identifier='file:'+f['id'];suffix=PurePosixPath(path).suffix.lower()
        kind='document' if suffix in ['.md','.rst','.txt'] else 'file'
        value={'id':identifier,'kind':kind,'label':PurePosixPath(path).name,'path':path,'path_id':f['id'],'language':'python' if suffix=='.py' else suffix.lstrip('.') or 'unknown','description':'','state':'INVENTORIED','analysis':'UNSUPPORTED_LANGUAGE' if suffix!='.py' else 'PENDING'}
        add_node(value);files[f['id']]=f
        parent=''
        for piece in PurePosixPath(path).parts[:-1]:
            current=(parent+'/' if parent else '')+piece
            if current not in directories:
                identifier_dir='directory:'+current;add_node({'id':identifier_dir,'kind':'directory','label':piece,'path':current,'state':'INVENTORIED'});edge(directories[parent],identifier_dir,'CONTAINS',{'method':'TRACKED_INVENTORY'});directories[current]=identifier_dir
            parent=current
        edge(directories[parent],identifier,'CONTAINS',evidence(f))
        if f['working'].get('sha256'):
            cache[f['id']]=source(reader,store,capture,f['id'],'working')
            if cache[f['id']].get('text') is not None:source_lines[f['id']]=cache[f['id']]['text'].encode('utf-8').splitlines(keepends=True)
        if suffix=='.py':
            name=module_name(path)
            module_files.setdefault(name,[]).append(f['id'])
    def parse(file):
        value=cache.get(file['id'],{})
        if value.get('text') is None:
            nodes['file:'+file['id']]['analysis']='UNAVAILABLE';unresolved.append({'file_id':'file:'+file['id'],'reason':'SOURCE_NOT_TEXT_OR_UNAVAILABLE'});return None
        try:
            tree=ast.parse(value['text'],filename=file['path'],type_comments=True)
            if sum(1 for _ in ast.walk(tree))>50000:raise RepositoryError('ANALYSIS_LIMIT','Python syntax tree limit exceeded',3)
            return tree
        except (SyntaxError,ValueError,RecursionError) as error:
            nodes['file:'+file['id']]['analysis']='PARSE_ERROR';unresolved.append({'file_id':'file:'+file['id'],'reason':'PYTHON_PARSE_ERROR','line':getattr(error,'lineno',None)});return None
    def define(file,tree):
        fileid='file:'+file['id'];nodes[fileid]['analysis']='PARSED';nodes[fileid]['description']=(ast.get_docstring(tree) or '')[:4000]
        def visit(parent,body,prefix):
            for item in body:
                if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    qual=prefix+item.name;identity=fileid+'::'+qual+'@'+str(item.lineno)
                    value={'id':identity,'kind':'symbol','label':qual,'path':file['path'],'path_id':file['id'],'symbol':qual,'description':(ast.get_docstring(item) or '')[:4000],
                           'state':'AST_DEFINITION','provenance':evidence(file,item),'symbol_kind':type(item).__name__}
                    add_node(value);symbols.setdefault((file['id'],qual),[]).append(identity);edge(parent,identity,'CONTAINS',evidence(file,item));visit(identity,item.body,qual+'.')
                else:
                    for field in ['body','orelse','finalbody']:
                        children=getattr(item,field,[])
                        if isinstance(children,list):visit(parent,children,prefix)
                    for handler in getattr(item,'handlers',[]):visit(parent,handler.body,prefix)
        visit(fileid,tree.body,'')
    for file in files.values():
        if file['path'].endswith('.py'):
            tree=parse(file)
            if tree:define(file,tree)
    def resolve_module(name):
        values=module_files.get(name,[])
        return values[0] if len(values)==1 else None
    def external(name):
        identity='external:'+name
        if identity not in nodes:add_node({'id':identity,'kind':'external_interface','label':name,'state':'IMPLEMENTATION_NOT_ANALYZED'})
        return identity
    for file in files.values():
        if not file['path'].endswith('.py'):continue
        tree=parse(file)
        if tree is None:continue
        fileid='file:'+file['id'];name=module_name(file['path']);package=name if file['path'].endswith('/__init__.py') else name.rpartition('.')[0]
        aliases={};rebound=set();topdefs={}
        for item in tree.body:
            if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                if item.name in topdefs:rebound.add(item.name)
                topdefs[item.name]=item.name
            elif isinstance(item,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
                rebound.update(n.id for n in ast.walk(item) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store))
            if isinstance(item,(ast.Import,ast.ImportFrom)):
                for alias in item.names:
                    if isinstance(item,ast.Import):mod=alias.name;symbol=None;bound=alias.asname or mod.split('.')[0];base=mod if alias.asname else bound
                    else:
                        prefix=package.split('.') if package else []
                        if item.level:prefix=prefix[:max(0,len(prefix)-item.level+1)]
                        else:prefix=[]
                        mod='.'.join([*prefix,*([item.module] if item.module else [])]);symbol=alias.name;bound=alias.asname or alias.name;base=mod
                        child='.'.join(x for x in [mod,symbol] if x)
                        if resolve_module(child):mod=child;symbol=None;base=mod
                    if bound in aliases or bound in topdefs:rebound.add(bound)
                    aliases[bound]=(base,symbol)
                    target=resolve_module(mod);to='file:'+target if target else external(mod or alias.name)
                    edge(fileid,to,'IMPORTS',evidence(file,item),segment(file,item) or 'import')
        counts={}
        class Bindings(ast.NodeVisitor):
            def bind(self,value):counts[value]=counts.get(value,0)+1
            def visit_FunctionDef(self,node):self.bind(node.name)
            visit_AsyncFunctionDef=visit_FunctionDef
            def visit_ClassDef(self,node):self.bind(node.name)
            def visit_Name(self,node):
                if isinstance(node.ctx,(ast.Store,ast.Del)):self.bind(node.id)
            def visit_Import(self,node):
                for item in node.names:self.bind(item.asname or item.name.split('.')[0])
            def visit_ImportFrom(self,node):
                for item in node.names:self.bind(item.asname or item.name)
        Bindings().visit(tree)
        rebound.update(key for key,count in counts.items() if count>1)
        if '*' in counts:rebound.update([*topdefs,*aliases])
        def find_symbol(target,qual):
            found=symbols.get((target,qual),[])
            return found[0] if len(found)==1 else None
        class Calls(ast.NodeVisitor):
            def __init__(self):self.scope=[];self.qual=[];self.classes=[]
            def visit_ClassDef(self,node):
                self.qual.append(node.name);self.classes.append(node.name)
                for child in node.body:self.visit(child)
                self.classes.pop();self.qual.pop()
            def visit_FunctionDef(self,node):
                self.qual.append(node.name);self.scope.append(local_bindings(node))
                for child in node.body:self.visit(child)
                self.scope.pop();self.qual.pop()
            visit_AsyncFunctionDef=visit_FunctionDef
            def visit_Lambda(self,node):
                unresolved.append({'file_id':fileid,'line':node.lineno,'reason':'DYNAMIC_LAMBDA_SCOPE'})
            def visit_Call(self,node):
                check()
                caller=find_symbol(file['id'],'.'.join(self.qual)) if self.qual else fileid
                chain=[];value=node.func
                while isinstance(value,ast.Attribute):chain.insert(0,value.attr);value=value.value
                if isinstance(value,ast.Name):chain.insert(0,value.id)
                to=None;kind='STATIC_CALL'
                if chain and isinstance(value,ast.Name) and chain[0] not in rebound:
                    base=chain[0];blocked=any(base in local for local in self.scope)
                    if len(chain)==1 and not blocked and base in topdefs:to=find_symbol(file['id'],base)
                    elif not blocked and base in aliases:
                        mod,imported=aliases[base];full='.'.join([mod,*([imported] if imported else []),*chain[1:]])
                        parts=full.split('.')
                        for at in range(len(parts)-1,0,-1):
                            candidate='.'.join(parts[:at])
                            target=resolve_module(candidate)
                            if target and full.startswith(candidate+'.'):
                                to=find_symbol(target,full[len(candidate)+1:]);break
                        if to is None and not resolve_module(mod):to=external(full);kind='REFERENCES_INTERFACE'
                if to and caller:edge(caller,to,kind,evidence(file,node),segment(file,node.func) or 'call')
                else:unresolved.append({'file_id':fileid,'line':node.lineno,'reason':'CALL_NOT_STATICALLY_RESOLVED','expression':segment(file,node.func) or ''})
                self.generic_visit(node)
        Calls().visit(tree)
    for file in files.values():
        text=cache.get(file['id'],{}).get('text')
        if not text or not file['path'].lower().endswith('.md'):continue
        for match in re.finditer(r'\[([^\]\n]+)\]\(([^)\n]+)\)',text):
            uri=urlsplit(match.group(2).strip())
            if uri.scheme or uri.netloc or not uri.path:continue
            target=posixpath.normpath(posixpath.join(posixpath.dirname(file['path']),unquote(uri.path)))
            if target.startswith('../') or target.startswith('/'):continue
            linked=next((f for f in files.values() if f['path']==target),None)
            if linked:
                ref=evidence(file);ref.update(method='MARKDOWN_LINK',start_line=text.count('\n',0,match.start())+1,end_line=text.count('\n',0,match.end())+1)
                edge('file:'+file['id'],'file:'+linked['id'],'DOCUMENTS',ref,match.group(1))
    # Explicit semantic mappings are data, not inferred feature definitions.
    for category,key in [('feature','features'),('term','terms')]:
        for item in settings.get(key,[]):
            if not isinstance(item,dict) or not all(isinstance(item.get(k),str) and item[k] for k in ['id','label','definition']):raise RepositoryError('INVALID_MAPPING','Feature/term needs id, label and definition')
            verified_refs=[]
            for ref in item.get('references',[]):
                linked=next((f for f in files.values() if f['path']==ref['path']),None)
                meta=cache.get(linked['id'],{}) if linked else {}
                start,end=ref.get('start_line',1),ref.get('end_line',ref.get('start_line',1))
                valid=bool(linked and meta.get('sha256') and end<=meta.get('lines',0))
                verified_refs.append(dict(ref,status='RESOLVED_SOURCE_RANGE' if valid else 'UNRESOLVED',file_id='file:'+linked['id'] if linked else None,sha256=meta.get('sha256')))
                if not valid:unresolved.append({'from':category+':'+item['id'],'reason':'MAPPING_REFERENCE_UNRESOLVED','reference':ref})
            identity=category+':'+item['id'];add_node({'id':identity,'kind':category,'label':item['label'],'description':item['definition'],'state':'EXPLICIT_MAPPING','references':verified_refs})
            for ref in verified_refs:
                if ref['status']=='RESOLVED_SOURCE_RANGE':
                    edge(identity,ref['file_id'],'DOCUMENTS',dict(ref,method='EXPLICIT_USER_MAPPING',capture_id=capture['capture_id']),ref['path'])
            for target in item.get('targets',[]):
                match=next((f for f in files.values() if f['path']==target.get('path')),None);to=None
                if match:to=find_symbol(match['id'],target['symbol']) if target.get('symbol') else 'file:'+match['id']
                if to:edge(identity,to,'IMPLEMENTS_FEATURE' if category=='feature' else 'DOCUMENTS',{'method':'EXPLICIT_USER_MAPPING','references':verified_refs})
                else:unresolved.append({'from':identity,'reason':'MAPPING_TARGET_UNRESOLVED','target':target})
    return validate_navigation({'schema':'calf.repository.navigation.v1','project':root,'capture_id':capture['capture_id'],'generated_at':now(),'nodes':list(nodes.values()),'edges':edges,'unresolved':unresolved,
            'source_captures':{key:{k:v for k,v in value.items() if k not in ['text','snapshot_path','current_path']} for key,value in cache.items()},
            'coverage':{'analyzers':[ANALYZER],'supported_languages':['python'],'files':len(files),'parsed_python':sum(n.get('analysis')=='PARSED' for n in nodes.values()),'unresolved':len(unresolved),'feature_definitions':'EXPLICIT_MAPPING_ONLY','runtime_verified':False}})
