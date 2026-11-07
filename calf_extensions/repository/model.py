"""Version identities and bounded data used by the Local Git extension."""
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone

SCHEMA = 'calf.repository.capture.v1'
MIN_GIT = (2, 43)
SOURCE_LIMIT = 1024 * 1024
TOTAL_SOURCE_LIMIT = 64 * SOURCE_LIMIT

class RepositoryError(Exception):
    def __init__(self, code, message, exit_code=1):
        super().__init__(message)
        self.code, self.exit_code = code, exit_code


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def oid(value, length=None):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', value) or length and len(value) != length:
        raise RepositoryError('INVALID_OID', 'Expected a full Git object ID')
    return value


def path_record(raw):
    if not isinstance(raw, bytes) or not raw or b'\0' in raw or raw.startswith(b'/') or any(p in (b'', b'.', b'..') for p in raw.split(b'/')):
        raise RepositoryError('INVALID_PATH', 'Invalid relative Git path')
    token = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    try:
        display = raw.decode('utf-8', errors='strict')
        readable = True
    except UnicodeError:
        display = repr(raw)[2:-1]
        readable = False
    return {'id': token, 'path': display, 'path_utf8': readable}


def path_bytes(token):
    if not isinstance(token, str) or len(token) > 16384 or not re.fullmatch(r'[A-Za-z0-9_-]+', token):
        raise RepositoryError('INVALID_PATH', 'Invalid path identity')
    try:
        raw = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
        record = path_record(raw)
    except (ValueError, TypeError) as error:
        raise RepositoryError('INVALID_PATH', 'Invalid path identity') from error
    if record['id'] != token:
        raise RepositoryError('INVALID_PATH', 'Noncanonical path identity')
    return raw


def classify(data):
    result = {'sha256': digest(data), 'size': len(data), 'text': None}
    if b'\0' in data:
        return dict(result, kind='binary')
    try:
        text = data.decode('utf-8-sig' if data.startswith(b'\xef\xbb\xbf') else 'utf-8', errors='strict')
    except UnicodeError:
        return dict(result, kind='encoding_unavailable')
    result.update(kind='lfs_pointer' if data.startswith(b'version https://git-lfs.github.com/spec/v1\n') else 'text', text=text,
                  encoding='utf-8-bom' if data.startswith(b'\xef\xbb\xbf') else 'utf-8',
                  lines=len(text.splitlines()), final_newline=text.endswith(('\n', '\r')),
                  crlf=text.count('\r\n'), lf=text.count('\n')-text.count('\r\n'))
    return result


def git_blob_oid(data, object_format):
    return hashlib.new(object_format, b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def validate_navigation(graph):
    if graph.get('schema')!='calf.repository.navigation.v1':
        raise RepositoryError('NAVIGATION_SCHEMA','Unsupported navigation schema')
    allowed={'project','directory','feature','term','document','module','file','symbol','external_interface','check','evidence'}
    nodes=graph.get('nodes');edges=graph.get('edges')
    if not isinstance(nodes,list) or not isinstance(edges,list):raise RepositoryError('NAVIGATION_SCHEMA','Nodes and edges must be arrays')
    by_id={}
    for node in nodes:
        identity=node.get('id')
        if not isinstance(identity,str) or not identity or identity in by_id or node.get('kind') not in allowed:
            raise RepositoryError('NAVIGATION_NODE','Invalid or duplicate graph entity')
        by_id[identity]=node
    if graph.get('project') not in by_id:raise RepositoryError('NAVIGATION_PROJECT','Missing project entity')
    seen=set()
    for edge in edges:
        if edge.get('id') in seen or edge.get('from') not in by_id or edge.get('to') not in by_id:raise RepositoryError('NAVIGATION_EDGE','Invalid or duplicate graph relation')
        seen.add(edge.get('id'));ref=edge.get('provenance',{})
        if not isinstance(ref,dict) or not ref.get('method'):raise RepositoryError('NAVIGATION_PROVENANCE','Relation needs discovery method')
        if edge.get('kind') in ['STATIC_CALL','IMPORTS','REFERENCES_INTERFACE','DOCUMENTS'] and ref.get('method')!='EXPLICIT_USER_MAPPING':
            if ref.get('file_id') not in by_id or not isinstance(ref.get('sha256'),str) or len(ref['sha256'])!=64:
                raise RepositoryError('NAVIGATION_PROVENANCE','Source relation needs captured file identity')
            if not isinstance(ref.get('start_line'),int) or not isinstance(ref.get('end_line'),int) or ref['start_line']<1 or ref['end_line']<ref['start_line']:
                raise RepositoryError('NAVIGATION_RANGE','Invalid source range')
    return graph


def validate_settings(value):
    if not isinstance(value,dict) or set(value)-{'label','description','features','terms'}:
        raise RepositoryError('INVALID_MAPPING','Unknown project-map fields')
    for key in ['label','description']:
        if key in value and (not isinstance(value[key],str) or len(value[key])>8192):raise RepositoryError('INVALID_MAPPING','Invalid project description')
    for key in ['features','terms']:
        items=value.get(key,[])
        if not isinstance(items,list) or len(items)>200:raise RepositoryError('INVALID_MAPPING','Too many project definitions')
        seen=set()
        for item in items:
            if not isinstance(item,dict) or set(item)-{'id','label','definition','references','targets'}:raise RepositoryError('INVALID_MAPPING','Unknown definition fields')
            if not isinstance(item.get('id'),str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,79}',item['id']) or item['id'] in seen:raise RepositoryError('INVALID_MAPPING','Invalid or duplicate definition identity')
            seen.add(item['id'])
            if not all(isinstance(item.get(k),str) and 0<len(item[k])<=8192 for k in ['label','definition']):raise RepositoryError('INVALID_MAPPING','Definition needs label and text')
            for field in ['references','targets']:
                entries=item.get(field,[])
                if not isinstance(entries,list) or len(entries)>100:raise RepositoryError('INVALID_MAPPING','Too many mapping references')
                for entry in entries:
                    allowed={'path','start_line','end_line'} if field=='references' else {'path','symbol'}
                    if not isinstance(entry,dict) or set(entry)-allowed or not isinstance(entry.get('path'),str):raise RepositoryError('INVALID_MAPPING','Invalid source mapping')
                    path_record(entry['path'].encode('utf-8'))
                    if field=='references':
                        start,end=entry.get('start_line',1),entry.get('end_line',entry.get('start_line',1))
                        if type(start)!=int or type(end)!=int or start<1 or end<start:raise RepositoryError('INVALID_MAPPING','Invalid definition line range')
                    elif 'symbol' in entry and (not isinstance(entry['symbol'],str) or not entry['symbol']):raise RepositoryError('INVALID_MAPPING','Invalid target symbol')
    return value
