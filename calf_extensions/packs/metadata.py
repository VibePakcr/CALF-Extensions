"""The shipped v1 schema subset, without an installed JSON Schema dependency.

Not a general JSON Schema service. Only our bundled schema is interpreted;
unknown keywords or external references fail closed. No pack code is imported.
"""
from pathlib import Path
import re
from .io import PackError,read,canonical

def _validate(value,schema,root,depth=0):
    if depth>40:raise PackError('metadata_depth_limit')
    if schema is True:return
    if schema is False:raise PackError('field_not_allowed')
    known={'$schema','$id','title','$defs','$ref','type','properties','required','additionalProperties','const','enum',
           'pattern','maxLength','minLength','items','minItems','maxItems','uniqueItems','minProperties','allOf','if','then','else'}
    if set(schema)-known:raise PackError('unsupported_schema_keyword')
    if '$ref' in schema:
        ref=schema['$ref']
        if not ref.startswith('#/$defs/'):raise PackError('external_schema_ref_forbidden')
        _validate(value,root['$defs'][ref[8:]],root,depth+1);return
    if 'const' in schema and (type(value)!=type(schema['const']) or value!=schema['const']):raise PackError('metadata_const')
    if 'enum' in schema and not any(type(value)==type(x) and value==x for x in schema['enum']):raise PackError('metadata_enum')
    kinds={'object':dict,'array':list,'string':str,'boolean':bool}
    if 'type' in schema and type(value)!=kinds[schema['type']]:raise PackError('metadata_type')
    if isinstance(value,dict):
        if set(schema.get('required',[]))-set(value):raise PackError('required_metadata_missing')
        props=schema.get('properties',{})
        if schema.get('additionalProperties') is False and set(value)-set(props):raise PackError('unknown_metadata_field')
        if len(value)<schema.get('minProperties',0):raise PackError('empty_metadata_object')
        for key,rule in props.items():
            if key in value:_validate(value[key],rule,root,depth+1)
    if isinstance(value,list):
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',10000):raise PackError('metadata_array_limit')
        if schema.get('uniqueItems') and len({canonical(x) for x in value})!=len(value):raise PackError('duplicate_metadata_item')
        if 'items' in schema:
            for item in value:_validate(item,schema['items'],root,depth+1)
    if isinstance(value,str):
        if not schema.get('minLength',0)<=len(value)<=schema.get('maxLength',65536):raise PackError('metadata_string_limit')
        if 'pattern' in schema and re.search(schema['pattern'],value) is None:raise PackError('metadata_pattern')
    for rule in schema.get('allOf',[]):_validate(value,rule,root,depth+1)
    if 'if' in schema:
        try:_validate(value,schema['if'],root,depth+1);branch='then'
        except PackError:branch='else'
        _validate(value,schema.get(branch,True),root,depth+1)

def numeric(version):
    if not re.fullmatch(r'(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){0,3}',version):raise PackError('unrecognized_version')
    parts=[int(x) for x in version.split('.')];return tuple(parts+[0]*(4-len(parts)))

def in_range(version,interval):return numeric(interval['minInclusive'])<=numeric(version)<numeric(interval['maxExclusive'])

def manifest(path):
    value=read(path);schema=read(Path(__file__).with_name('manifest.schema.json'))
    _validate(value,schema,schema)
    for group in ('dependencies','entryPoints','modes'):
        ids=[x['id'] for x in value[group]]
        if len(ids)!=len(set(ids)):raise PackError('duplicate_metadata_id')
    dependencies={x['id'] for x in value['dependencies']};entries={x['id']:x for x in value['entryPoints']}
    intervals=[x['versionRange'] for x in value['dependencies'] if 'versionRange' in x]
    transport={'cli':{'python-module','python-callable','package-file'},'python':{'python-module','python-callable'},
        'stdio-mcp':{'core-command','python-module','package-file'},'loopback-http':{'python-module','package-file'},'offline-html':{'package-file'}}
    for row in entries.values():
        if row['status']=='implemented' and row['targetKind'] not in transport[row['transport']]:raise PackError('entry_transport_mismatch')
    for mode in value['modes']:
        if not set(mode['dependencies'])<=dependencies or not set(mode['entryPoints'])<=set(entries):raise PackError('dangling_metadata_reference')
        intervals+=list(mode.get('core',{}).get('editions',{}).values())
        if mode['status']=='implemented' and any(entries[e]['status']!='implemented' for e in mode['entryPoints']):raise PackError('planned_entry_in_implemented_mode')
    for interval in intervals:
        if numeric(interval['minInclusive'])>=numeric(interval['maxExclusive']):raise PackError('inverted_version_interval')
    return value
