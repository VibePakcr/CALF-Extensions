"""Explicit local probes. First driver: the existing FFmpeg scene pack."""
import ast
from datetime import datetime,timezone
import platform
import re
from .io import PackError,physical,sha,read,decode,run,digest
from .metadata import in_range

def platform_id():
    osname={'Darwin':'macos','Windows':'windows','Linux':'linux'}.get(platform.system(),'unknown')
    arch={'arm64':'arm64','aarch64':'arm64','x86_64':'x64','amd64':'x64'}.get(platform.machine().lower(),'unknown')
    return osname+'-'+arch

def observe(package,metadata,mode_id,environment):
    mode=next((m for m in metadata['modes'] if m['id']==mode_id),None)
    if mode is None:raise PackError('mode_not_found')
    if not isinstance(environment,dict):raise PackError('environment_object_required')
    report={'schema':'calf.pack.compatibility.v1','platform':platform_id(),'mode':mode_id,'status':'UNKNOWN',
        'coreStatus':'UNKNOWN' if mode['supervised'] else 'NOT_REQUIRED','observedAt':datetime.now(timezone.utc).isoformat(),
        'dependencies':[],'fingerprints':{},'environment':dict(environment),'reasons':[]}
    if metadata['id']=='calf.repository.local-git':
        from .repository import observe as repository_observe
        return repository_observe(package,metadata,mode,environment,report)
    if metadata['id']!='calf.media.ffmpeg' or mode_id!='scenes' or mode['status']!='implemented':
        report['reasons'].append('driver_not_implemented');return report
    if set(environment)!={'python','sdk','calf','edition','ffmpeg','ffprobe'}:raise PackError('explicit_ffmpeg_environment_required')
    if environment['edition'] not in ('harness','workbench'):raise PackError('explicit_core_edition_required')
    def pin(path):
        p=physical(path);report['fingerprints'][str(p)]=sha(p);return p
    dependencies={d['id']:d for d in metadata['dependencies']}
    for key in mode['dependencies']:
        row={'id':key,'status':'UNKNOWN'}
        try:
            d=dependencies[key]
            if key=='python':
                p=pin(environment['python'])
                data=decode(run([p,'-I','-S','-B','-X','utf8','-c','import sys,json;print(json.dumps({"version":".".join(map(str,sys.version_info[:3])),"utf8":sys.stdout.encoding}))']))
                version=data['version'];features={'stdlib','utf8'} if data['utf8'].lower()=='utf-8' else {'stdlib'}
                original=version
            elif key=='calf-sdk':
                root=physical(environment['sdk'],directory=True);init=pin(root/'calf_sdk/__init__.py')
                if init.stat().st_size>65536:raise PackError('sdk_metadata_size_limit')
                source=init.read_text('utf8');tree=ast.parse(source)
                version=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in n.targets) and isinstance(n.value,ast.Constant))
                for name in ('client.py','adapter.py','work.py'):pin(root/'calf_sdk'/name)
                features={'public-universal-work-v1'} if version=='0.2.1' else set();original=version
            elif key in ('ffmpeg','ffprobe'):
                p=pin(environment[key]);original=run([p,'-version']).decode('utf8').splitlines()[0]
                match=re.match(key+r' version ([0-9]+(?:\.[0-9]+){1,3})(?:[- .]|$)',original)
                if not match:raise PackError('unrecognized_tool_version')
                version=match[1];features=set()
                if key=='ffmpeg':
                    encoders=run([p,'-hide_banner','-encoders']).decode('utf8')
                    filters=run([p,'-hide_banner','-filters']).decode('utf8')
                    protocols=run([p,'-hide_banner','-protocols']).decode('utf8')
                    for name in ('libx264','aac'):
                        if re.search(r'(?m)^\s*[A-Z.]{6}\s+'+name+r'\s',encoders):features.add(name)
                    for name in ('blackdetect','silencedetect'):
                        if re.search(r'(?m)^\s*[A-Z.]{2,3}\s+'+name+r'\s',filters):features.add(name)
                    if re.search(r'(?m)^\s+file\s*$',protocols):features.add('file-only-input')
                elif re.search(r'(?m)^\s*-print_format\s',run([p,'-hide_banner','-h']).decode('utf8')):
                    features.add('json-stream-inventory')
            else:raise PackError('dependency_driver_not_implemented')
            row.update(version=version,originalVersion=original,features=sorted(features))
            row['status']='COMPATIBLE' if in_range(version,d['versionRange']) else 'INCOMPATIBLE'
            if row['status']=='COMPATIBLE' and set(d['requiredFeatures'])-features:row.update(status='UNKNOWN',reason='capability_not_observed')
        except FileNotFoundError as e:row.update(status='INCOMPATIBLE',reason='dependency_missing')
        except (OSError,ValueError,StopIteration,KeyError,TypeError,SyntaxError) as e:row.update(status='UNKNOWN',reason=str(e)[:200])
        report['dependencies'].append(row)
    try:
        calf=pin(environment['calf']);core=decode(run([calf,'--version'],limit=65536))
        report['core']=core
        interval=mode['core']['editions'].get(environment['edition'])
        report['coreStatus']='COMPATIBLE' if interval and in_range(core['version'],interval) else 'INCOMPATIBLE'
        qualification=read(package/'VERIFICATION.json')
        qualified=qualification['platforms'][platform_id()]['cores'][environment['edition']]
        if qualified['sha256']!=report['fingerprints'][str(calf)]:
            if report['coreStatus']=='COMPATIBLE':report['coreStatus']='UNKNOWN'
            report['reasons'].append('core_binary_not_qualified')
        observed=qualification['platforms'][platform_id()]
        expected=observed.get('FFmpeg') or re.match(r'ffmpeg version ([0-9.]+)',observed['tools']['ffmpeg'])[1]
        if next(r for r in report['dependencies'] if r['id']=='ffmpeg').get('version')!=expected:
            report['reasons'].append('tool_platform_combination_not_qualified')
    except (OSError,ValueError,KeyError,TypeError) as e:
        report['coreStatus']='UNKNOWN';report['reasons'].append('core_or_platform_not_qualified:'+str(e)[:120])
    if mode['network']!='none':report['reasons'].append('network_mode_not_implemented')
    states=[r['status'] for r in report['dependencies']]+[report['coreStatus']]
    report['status']='INCOMPATIBLE' if 'INCOMPATIBLE' in states else 'UNKNOWN' if 'UNKNOWN' in states or report['reasons'] else 'COMPATIBLE'
    # Detect a change during probes, not only at later activation.
    try:changed=any(sha(p)!=h for p,h in report['fingerprints'].items())
    except OSError:changed=True
    if changed:report['status']='UNKNOWN';report['reasons'].append('dependency_changed_during_probe')
    return report

def recheck_lock(lock):
    if lock.get('schema')!='calf.pack.lock.v1' or lock.get('compatibility',{}).get('status')!='COMPATIBLE':raise PackError('compatible_lock_required')
    if lock['compatibility']['platform']!=platform_id():raise PackError('lock_platform_changed')
    for path,expected in lock['compatibility']['fingerprints'].items():
        if sha(path)!=expected:raise PackError('dependency_identity_changed')
