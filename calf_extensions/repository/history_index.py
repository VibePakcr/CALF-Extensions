"""Bounded, disposable views of explicitly selected CALF history; never a writer.

The native core owns schema/hash-chain validation and completion. This module
only checks envelope continuity and builds version-bound navigation projections.
"""
from collections import deque
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import time
import unicodedata
from .model import RepositoryError

SCHEMA = 'calf.repository.history-index.v1'
MARKER = b'<script type="application/json" data-calf="record">'
END = b'</script>'
CHUNK = 32768
RECORD_LIMIT = 1024 * 1024
SOURCE_LIMIT = 256 * 1024 * 1024
PAGE = 32
RECENT = 20
SEARCH_BYTES = 8 * 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}\Z')

def require(condition, code):
    if not condition:
        raise RepositoryError(code, 'History view unavailable: ' + code)

def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')

def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'HISTORY_DUPLICATE_KEY')
            value[key] = item
        return value
    def constant(_):
        raise RepositoryError('HISTORY_JSON', 'Nonfinite history number')
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs, parse_constant=constant)

def physical(path, directory=False):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and path.resolve(strict=True) == path,
            'HISTORY_PHYSICAL_PATH_REQUIRED')
    require(path.is_dir() if directory else path.is_file(), 'HISTORY_PATH_TYPE')
    return path

def stamp(path):
    st = path.stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]

def digest_file(path):
    h = hashlib.sha256(); count = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            count += len(block)
            require(count <= SOURCE_LIMIT, 'HISTORY_SOURCE_LIMIT')
            h.update(block)
    return h.hexdigest(), count

def read_small(path, limit, metrics=None):
    physical(path)
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'HISTORY_VIEW_LIMIT')
    if metrics is not None:
        metrics['indexBytesRead'] += len(raw)
    return raw

def save_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()

def records(path, observation):
    """Read fixed v1 inert record blocks, retaining exact byte offsets/digests.

    Unsupported markup is not guessed into a compatible native journal.
    """
    h = hashlib.sha256(); total = 0; buffer = b''; base = 0; active = False
    with path.open('rb') as stream:
        while True:
            block = stream.read(CHUNK)
            if block:
                h.update(block); total += len(block)
                require(total <= SOURCE_LIMIT, 'HISTORY_SOURCE_LIMIT')
                buffer += block
            while True:
                if not active:
                    at = buffer.find(MARKER)
                    if at < 0:
                        keep = len(MARKER) - 1
                        if len(buffer) > keep:
                            base += len(buffer) - keep; buffer = buffer[-keep:]
                        break
                    cut = at + len(MARKER); base += cut; buffer = buffer[cut:]; active = True
                end = buffer.find(END)
                if end < 0:
                    require(len(buffer) <= RECORD_LIMIT + len(END), 'HISTORY_RECORD_LIMIT')
                    break
                require(end <= RECORD_LIMIT, 'HISTORY_RECORD_LIMIT')
                raw = buffer[:end]
                yield base, raw, decode(raw)
                cut = end + len(END); base += cut; buffer = buffer[cut:]; active = False
            if not block:
                require(not active, 'HISTORY_TRUNCATED_RECORD')
                break
    observation.update(sha256=h.hexdigest(), bytes=total)

def module_map(path, raw=None):
    value = decode(read_small(physical(path), 65536) if raw is None else raw)
    require(set(value) == {'schema','modules'} and value['schema'] == 'calf.repository.history-modules.v1', 'HISTORY_MAPPING')
    rows = value['modules']; require(isinstance(rows,list) and 1 <= len(rows) <= 64, 'HISTORY_MAPPING')
    result = {}
    for row in rows:
        require(isinstance(row,dict) and set(row) <= {'id','label','paths','tasks','dependsOn'}, 'HISTORY_MAPPING')
        key = row.get('id')
        require(isinstance(key,str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',key)
                and key != 'unassigned' and key not in result, 'HISTORY_MODULE_ID')
        require(isinstance(row.get('label'),str) and 0 < len(row['label']) <= 120, 'HISTORY_MAPPING')
        paths = row.get('paths',[]); require(isinstance(paths,list) and len(paths) <= 64, 'HISTORY_MAPPING')
        for name in paths:
            require(isinstance(name,str) and 0 < len(name) <= 512 and '\\' not in name
                    and not PurePosixPath(name).is_absolute() and all(p not in ('','.','..') for p in name.split('/')), 'HISTORY_MAPPING_PATH')
        deps = row.get('dependsOn',[])
        tasks = row.get('tasks',[])
        require(isinstance(tasks,list) and len(tasks) <= 256 and all(isinstance(t,str) and 0 < len(t) <= 256 for t in tasks)
                and len(set(tasks)) == len(tasks) and (paths or tasks), 'HISTORY_MAPPING')
        require(isinstance(deps,list) and len(deps) <= 16 and len(set(deps)) == len(deps)
                and all(isinstance(d,str) for d in deps), 'HISTORY_MAPPING')
        result[key] = dict(row,paths=paths,tasks=tasks,dependsOn=deps)
    require(all(d in result and d != key for key,row in result.items() for d in row['dependsOn']), 'HISTORY_MAPPING_DEPENDENCY')
    return result

def native_status(calf, history, task):
    """The existing read-only `calf status WORKSPACE TASK` interface.

    Never recompute the core's proprietary hash/schema algorithm or infer PASS
    from a stored word, process exit code, or this index's contents.
    """
    calf = physical(calf)
    require(history.name == 'history.html' and isinstance(task,str) and 0 < len(task) <= 256, 'HISTORY_NATIVE_ARGUMENT')
    binary_sha, _ = digest_file(calf)
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        child = subprocess.Popen([str(calf),'status',str(history.parent),task], stdout=output, stderr=errors, shell=False)
        try:
            deadline = time.monotonic() + 15
            while child.poll() is None:
                require(os.fstat(output.fileno()).st_size <= 65536 and os.fstat(errors.fileno()).st_size <= 65536, 'HISTORY_NATIVE_LIMIT')
                require(time.monotonic() < deadline, 'HISTORY_NATIVE_TIMEOUT')
                try:child.wait(timeout=.05)
                except subprocess.TimeoutExpired:pass
            require(child.returncode == 0, 'HISTORY_NATIVE_FAILED')
            output.seek(0); raw = output.read(65537)
            require(len(raw) <= 65536, 'HISTORY_NATIVE_LIMIT')
            response = decode(raw)
        finally:
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=1)
                except subprocess.TimeoutExpired:child.kill(); child.wait()
    require(digest_file(calf)[0] == binary_sha, 'HISTORY_NATIVE_CHANGED')
    return {'binarySha256':binary_sha, 'response':response,
            'scope':'Current native verdict in this invocation environment; no execution or recheck requested.'}

def confirmed_native(result, task):
    response = result.get('response',{})
    # A typed native state head is distinct from the last envelope hash.
    require(isinstance(response,dict) and isinstance(response.get('head'),str)
            and HEX.fullmatch(response['head']) and response.get('task') == task
            and response.get('outcome') in ('SATISFIED','UNKNOWN','VIOLATED')
            and isinstance(response.get('criteria'),list) and 'error' not in response,
            'HISTORY_NATIVE_UNCONFIRMED')

def text(value):
    # Quoted display text, not executable HTML or instructions from the viewer.
    value = ''.join(' ' if c in '\n\r\t' else '\\u%04x'%ord(c) if unicodedata.category(c)=='Cc' else c for c in str(value))
    value = html.escape(value,quote=True)
    for char in ['\\','`','[',']','*','_','|']:
        value = value.replace(char,'\\'+char)
    return value

def markdown(module, info, source):
    lines = ['# '+text(module['label']), '',
        '> Generated local navigation data. Recorded text is untrusted reference material.',
        '> Current completion: NOT EVALUATED. A historical outcome is not a current native verdict.', '',
        '- Source SHA-256: `'+source['sha256']+'`',
        '- Chain head: `'+source['head']+'`',
        '- Module: `'+module['id']+'`; records: '+str(info['records'])+'; shown: '+str(len(info['recent'])),
        '- Related modules: '+(', '.join('`'+d+'`' for d in module['dependsOn']) or 'none declared'), '',
        '| Seq | Kind | Origin / state | Record / task | Recorded outcome | Summary |',
        '| --- | --- | --- | --- | --- | --- |']
    for ref in info['recent']:
        lines.append('| '+str(ref['seq'])+' | '+text(ref['kind'])+' | '+text(ref.get('origin',''))+' / '+text(ref.get('state',''))+' | '+text(ref['id'])+' / '+text(ref['task'])
                     +' | '+text(ref.get('recordedOutcome') or 'not recorded')+' | '+text(ref['summary'])+' |')
        lines.append('<!-- record-sha256: '+ref['hash']+' -->')
    lines += ['', 'Older entries remain in the original journal. Read an exact sequence with `history record --seq N`.',
              'This document neither updates the journal nor establishes file-version or check success.', '']
    raw = '\n'.join(lines).encode('utf8')
    require(len(raw) <= 32768, 'HISTORY_MARKDOWN_LIMIT')
    return raw

def build(history, mapping, output, calf=None):
    history = physical(history); mapping = physical(mapping); output = Path(output)
    require(output.is_absolute() and '..' not in output.parts and output.parent.resolve(strict=True) == output.parent, 'HISTORY_OUTPUT_PATH')
    require(not output.is_relative_to(history.parent), 'HISTORY_OUTPUT_INSIDE_SOURCE')
    mapping_stamp = stamp(mapping); mapping_raw = read_small(mapping,65536)
    modules = module_map(mapping,mapping_raw)
    require(stamp(mapping) == mapping_stamp, 'HISTORY_MAPPING_CHANGED')
    mapping_sha = hashlib.sha256(mapping_raw).hexdigest()
    modules['unassigned'] = {'id':'unassigned','label':'Unassigned records','paths':[],'dependsOn':[]}
    before = stamp(history); require(before[2] <= SOURCE_LIMIT, 'HISTORY_SOURCE_LIMIT')
    output.mkdir(mode=0o700)  # Exclusive; partial builds never replace an index.
    (output/'pages').mkdir(mode=0o700)
    tasks = {}; seen = set(); last = None; count = 0; page = []; page_shas = []; first_task = None
    infos = {key:{'records':0,'recent':deque(maxlen=RECENT)} for key in modules}
    observed = {}
    for offset, raw, envelope in records(history, observed):
        require(isinstance(envelope,dict) and set(envelope) == {'seq','hash','prev','record'}, 'HISTORY_ENVELOPE')
        require(type(envelope['seq']) is int and envelope['seq'] == count+1 and count < 100000, 'HISTORY_SEQUENCE')
        require(all(isinstance(envelope[k],str) and HEX.fullmatch(envelope[k]) for k in ['hash','prev']), 'HISTORY_DIGEST')
        require(last is None or envelope['prev'] == last, 'HISTORY_CHAIN_CONTINUITY')
        row = envelope['record']; require(isinstance(row,dict), 'HISTORY_RECORD')
        identity = row.get('id'); task = row.get('task','')
        require(isinstance(identity,str) and 0 < len(identity) <= 256, 'HISTORY_RECORD_ID')
        identity_key = hashlib.sha256(identity.encode('utf8')).digest()
        require(identity_key not in seen, 'HISTORY_RECORD_ID')
        require(isinstance(task,str) and len(task) <= 256 and isinstance(row.get('kind'),str) and len(row['kind']) <= 64, 'HISTORY_RECORD')
        seen.add(identity_key); data = row.get('data',{})
        require(isinstance(data,dict), 'HISTORY_RECORD')
        if row['kind'] == 'TASK':
            require(len(tasks) < 4096, 'HISTORY_TASK_LIMIT')
            scope = data.get('scope',[]); require(isinstance(scope,list) and len(scope) <= 64 and all(isinstance(s,str) for s in scope), 'HISTORY_SCOPE')
            membership = [key for key,module in modules.items() if identity in module.get('tasks',[]) or
                          any(s == prefix or s.startswith(prefix+'/') or prefix.startswith(s+'/')
                              for s in scope if s for prefix in module['paths'])]
            tasks[identity] = membership or ['unassigned']
            if first_task is None:first_task = identity
        membership = tasks.get(task,['unassigned'])
        count += 1; last = envelope['hash']
        ref = {'seq':count,'id':identity,'task':task,'kind':row['kind'],'hash':last,'prev':envelope['prev'],
            'origin':str(row.get('origin',''))[:64],'state':str(row.get('state',''))[:64],
            'offset':offset,'length':len(raw),'rawSha256':hashlib.sha256(raw).hexdigest(),
            'summary':str(row.get('body',''))[:160], 'modules':membership,
            'recordedOutcome':data.get('outcome') if data.get('outcome') in ('SATISFIED','UNKNOWN','VIOLATED') else None}
        page.append(ref)
        for key in membership:
            infos[key]['records'] += 1; infos[key]['recent'].append(ref)
        if len(page) == PAGE:
            page_raw = encode(page); require(len(page_raw) <= 256*1024, 'HISTORY_PAGE_LIMIT')
            page_shas.append(save_new(output/'pages'/('%06d.json'%len(page_shas)),page_raw)); page=[]
    require(count > 0, 'HISTORY_RECORDS_UNAVAILABLE')
    if page:
        page_raw = encode(page); require(len(page_raw) <= 256*1024, 'HISTORY_PAGE_LIMIT')
        page_shas.append(save_new(output/'pages'/('%06d.json'%len(page_shas)),page_raw))
    require(stamp(history) == before, 'HISTORY_SOURCE_CHANGED')
    source = {'path':str(history),'stamp':before,'sha256':observed['sha256'],'bytes':observed['bytes'],
              'records':count,'head':last,'chainValidation':'CONTINUITY_ONLY','nativeValidation':None}
    if calf is not None:
        require(first_task is not None, 'HISTORY_NATIVE_TASK_REQUIRED')
        native = native_status(calf,history,first_task)
        confirmed_native(native,first_task)
        after_hash,after_bytes = digest_file(history)
        require(after_hash == observed['sha256'] and stamp(history) == before, 'HISTORY_SOURCE_CHANGED')
        require(native['response']['head'] == after_hash, 'HISTORY_NATIVE_UNCONFIRMED')
        source.update(chainValidation='NATIVE_CONFIRMED_AT_BUILD',nativeValidation=native,
                      nativeStateHead=native['response']['head'])
    else:after_bytes = 0
    summaries = []
    for key,module in modules.items():
        info = infos[key]
        raw = markdown(module,info,source); filename = 'sub_'+key+'.md'
        digest = save_new(output/filename,raw)
        summaries.append({'id':key,'label':module['label'],'dependsOn':module['dependsOn'],
            'records':info['records'],'shown':len(info['recent']),'omitted':max(0,info['records']-RECENT),
            'markdown':filename,'sha256':digest,'bytes':len(raw)})
    require(stamp(history) == before, 'HISTORY_SOURCE_CHANGED')
    require(stamp(mapping) == mapping_stamp and digest_file(mapping)[0] == mapping_sha, 'HISTORY_MAPPING_CHANGED')
    manifest = {'schema':SCHEMA,'source':source,'mappingSha256':mapping_sha,
        'modules':summaries,'pageSha256':page_shas,'pageSize':PAGE,
        'completionAuthority':'NATIVE_CORE_ONLY','currentCompletion':'NOT_EVALUATED',
        'limits':{'recentPerModule':RECENT,'recordBytes':RECORD_LIMIT,'relatedModules':4},
        'metrics':{'sourceBytesRead':observed['bytes']+after_bytes,'recordsIndexed':count,'nativeIOBytesMeasured':calf is None}}
    raw = encode(manifest); require(len(raw) <= 256*1024, 'HISTORY_MANIFEST_LIMIT')
    save_new(output/'INDEX.json',raw)  # Final commit marker for this new view.
    return {'state':'INDEXED','index':str(output),'records':count,'modules':len(modules),
            'sourceSha256':source['sha256'],'chainValidation':source['chainValidation'],
            'currentCompletion':'NOT_EVALUATED','metrics':manifest['metrics']}

class HistoryView:
    def __init__(self,index,verify_source=False):
        self.root = physical(index,directory=True)
        self.metrics = {'indexBytesRead':0,'sourceBytesRead':0}
        self.index = decode(read_small(self.root/'INDEX.json',256*1024,self.metrics))
        require(self.index.get('schema') == SCHEMA and self.index.get('pageSize') == PAGE, 'HISTORY_INDEX_SCHEMA')
        self.source = self.index['source']; self.path = physical(self.source['path'])
        self.freshness = 'STAT_MATCH'
        require(stamp(self.path) == self.source['stamp'], 'HISTORY_INDEX_STALE')
        if verify_source:
            digest,count = digest_file(self.path); self.metrics['sourceBytesRead'] += count
            require(digest == self.source['sha256'], 'HISTORY_SOURCE_DIGEST')
            self.freshness = 'SHA256_MATCH'
        rows = self.index['modules']; require(isinstance(rows,list) and len(rows) <= 65, 'HISTORY_INDEX_SCHEMA')
        self.modules = {r['id']:r for r in rows}
        require(len(rows) == len(self.modules), 'HISTORY_INDEX_SCHEMA')

    def stable(self):
        require(stamp(self.path) == self.source['stamp'], 'HISTORY_INDEX_STALE')

    def listing(self):
        self.stable()
        return {'sourceSha256':self.source['sha256'],'head':self.source['head'],
            'freshness':self.freshness,'currentCompletion':'NOT_EVALUATED',
            'modules':[{k:r[k] for k in ['id','label','records','shown','omitted','dependsOn']} for r in self.modules.values()],
            'metrics':self.metrics}

    def module(self,key,related=False):
        require(key in self.modules, 'HISTORY_MODULE_NOT_FOUND')
        keys = [key] + (self.modules[key]['dependsOn'][:4] if related else [])
        docs = []
        for selected in keys:
            require(selected in self.modules and re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',selected), 'HISTORY_INDEX_SCHEMA')
            row = self.modules[selected]
            require(row['markdown'] == 'sub_'+selected+'.md', 'HISTORY_INDEX_SCHEMA')
            raw = read_small(self.root/row['markdown'],32768,self.metrics)
            require(hashlib.sha256(raw).hexdigest() == row['sha256'], 'HISTORY_PROJECTION_CHANGED')
            docs.append({'module':selected,'markdown':raw.decode('utf8'),'records':row['records'],'omitted':row['omitted']})
        self.stable()
        return {'documents':docs,'freshness':self.freshness,'sourceSha256':self.source['sha256'],
            'currentCompletion':'NOT_EVALUATED','relatedOmitted':max(0,len(self.modules[key]['dependsOn'])-4) if related else 0,
            'metrics':self.metrics}

    def record(self,seq):
        require(type(seq) is int and 1 <= seq <= self.source['records'], 'HISTORY_SEQUENCE')
        page = (seq-1)//PAGE
        raw = read_small(self.root/'pages'/('%06d.json'%page),256*1024,self.metrics)
        require(hashlib.sha256(raw).hexdigest() == self.index['pageSha256'][page], 'HISTORY_PROJECTION_CHANGED')
        ref = decode(raw)[(seq-1)%PAGE]
        require(ref['seq'] == seq and type(ref['length']) is int and 0 < ref['length'] <= RECORD_LIMIT
                and type(ref['offset']) is int and 0 <= ref['offset'] <= self.source['bytes']-ref['length'], 'HISTORY_INDEX_SCHEMA')
        with self.path.open('rb') as stream:
            stream.seek(ref['offset']); content = stream.read(ref['length'])
        self.metrics['sourceBytesRead'] += len(content)
        require(hashlib.sha256(content).hexdigest() == ref['rawSha256'], 'HISTORY_RECORD_CHANGED')
        envelope = decode(content)
        require(envelope['seq'] == seq and envelope['hash'] == ref['hash'] and envelope['record']['id'] == ref['id'], 'HISTORY_RECORD_CHANGED')
        self.stable()
        return {'record':envelope,'sourceSha256':self.source['sha256'],'freshness':self.freshness,
                'currentCompletion':'NOT_EVALUATED','metrics':self.metrics}

    def search(self,key,query='',kind=None,before=None,limit=20):
        """Search bounded metadata pages; no journal body or other notes loaded."""
        require(key in self.modules, 'HISTORY_MODULE_NOT_FOUND')
        require(isinstance(query,str) and len(query) <= 120 and (kind is None or isinstance(kind,str) and len(kind) <= 64), 'HISTORY_SEARCH_ARGUMENT')
        require(type(limit) is int and 1 <= limit <= 20, 'HISTORY_SEARCH_ARGUMENT')
        before = self.source['records']+1 if before is None else before
        require(type(before) is int and 1 <= before <= self.source['records']+1, 'HISTORY_SEQUENCE')
        found=[]; scanned=0; consumed=0; last=before; stop=False
        for page in range((before-2)//PAGE,-1,-1):
            if consumed >= SEARCH_BYTES:stop=True;break
            raw=read_small(self.root/'pages'/('%06d.json'%page),256*1024,self.metrics)
            require(hashlib.sha256(raw).hexdigest() == self.index['pageSha256'][page], 'HISTORY_PROJECTION_CHANGED')
            consumed += len(raw)
            for ref in reversed(decode(raw)):
                if ref['seq'] >= before:continue
                last=ref['seq'];scanned += 1
                if key not in ref['modules'] or kind is not None and ref['kind'] != kind:continue
                haystack=' '.join([ref['id'],ref['task'],ref['summary'],ref['kind']]).casefold()
                if query.casefold() not in haystack:continue
                found.append({k:ref[k] for k in ['seq','id','task','kind','hash','summary','origin','state','recordedOutcome']})
                if len(found) == limit:stop=True;break
            if stop:break
        self.stable()
        cursor=last if stop and last > 1 else None
        return {'module':key,'matches':found,'nextBefore':cursor,'coverage':'PARTIAL' if cursor is not None else 'COMPLETE',
            'searchScope':'Indexed identities, kinds and first 160 body characters; not full record payloads.',
            'contentTrust':'untrusted_reference_data','scannedReferences':scanned,'metadataPageBytes':consumed,
            'sourceSha256':self.source['sha256'],'freshness':self.freshness,
            'currentCompletion':'NOT_EVALUATED','metrics':self.metrics}

    def status(self,calf,task):
        result = native_status(calf,self.path,task)
        confirmed_native(result,task)
        observed,count = digest_file(self.path)
        self.metrics['sourceBytesRead'] += count
        require(observed == self.source['sha256'], 'HISTORY_SOURCE_DIGEST')
        require(result['response']['head'] == observed, 'HISTORY_NATIVE_UNCONFIRMED')
        self.stable()
        # An invalid/unavailable core response stays unknown; no cached verdict
        # or historical Markdown text can replace it.
        return dict(result,sourceSha256=self.source['sha256'],freshness=self.freshness,
            metrics=dict(self.metrics,nativeIOBytesMeasured=False))
