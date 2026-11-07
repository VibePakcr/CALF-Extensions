"""Local, side-by-side pack storage. Native work records are never edited here."""
import os
from pathlib import Path
import re
import stat
import tarfile
import uuid
import zipfile
from .io import PackError,physical,sha,read,relative,portable_key,token,decode,canonical,digest,atomic,mutex,run,sync_directory
from .metadata import manifest
from .compatibility import observe,recheck_lock

ID=re.compile(r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$')
VERSION=re.compile(r'^[0-9A-Za-z.+-]{1,96}$')

def inventory(root):
    root=physical(root,directory=True);rows={};seen=set()
    with physical(root/'FILES.sha256').open('rb') as f:raw=f.read(1048577)
    if len(raw)>1048576:raise PackError('inventory_size_limit')
    for line in raw.decode('utf8').splitlines():
        if len(line)<67 or line[64:66]!='  ':raise PackError('invalid_file_inventory')
        expected=token(line[:64]);name=relative(line[66:]);key=portable_key(name)
        if key in seen or name=='FILES.sha256':raise PackError('duplicate_inventory_path')
        rows[name]=expected;seen.add(key)
    actual={};size=0
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            p=Path(parent)/name
            if p.is_symlink():raise PackError('linked_payload_directory')
        for name in files:
            p=Path(parent)/name;name=relative(p.relative_to(root).as_posix())
            s=p.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise PackError('linked_or_special_payload_file')
            size+=s.st_size
            if len(actual)>=4096 or size>256*1024*1024:raise PackError('payload_size_limit')
            actual[name]=sha(p)
    actual.pop('FILES.sha256',None)
    if actual!=rows:raise PackError('payload_inventory_mismatch')
    return rows

def package_metadata(root):
    meta=manifest(root/'pack.json')
    for name in list(meta['documentation'].values())+[meta['resources']['limitsDocument'],meta['verification']['specification'],meta['recovery']['specification']]+meta['verification']['runtimeEvidence']+meta['verification']['lifecycleEvidence']:
        physical(root/relative(name.split('#')[0]))
    for entry in meta['entryPoints']:
        if entry['status']!='implemented':continue
        if entry['targetKind'].startswith('python-'):
            name=entry['target'].split(':')[0].replace('.','/')
            if not (root/(name+'.py')).is_file():physical(root/name/'__init__.py')
            else:physical(root/(name+'.py'))
        elif entry['targetKind']=='package-file':physical(root/relative(entry['target']))
    read(root/'qualification.json')
    return meta

def extract(archive,destination):
    destination.mkdir();seen=set();prefixes={};count=0;total=0
    def save(name,size,stream,is_dir=False):
        nonlocal count,total
        name=name.rstrip('/') if is_dir else name;relative(name)
        key=portable_key(name)
        if key in seen:raise PackError('duplicate_archive_path')
        seen.add(key);count+=1;total+=size
        if count>4096 or total>256*1024*1024:raise PackError('archive_size_limit')
        parts=name.split('/')
        for i in range(1,len(parts)+1):
            prefix='/'.join(parts[:i]);folded=portable_key(prefix)
            if folded in prefixes and prefixes[folded]!=prefix:raise PackError('case_colliding_archive_path')
            prefixes[folded]=prefix
        target=destination/name
        if is_dir:target.mkdir(parents=True,exist_ok=True);return
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:
            remaining=size
            while remaining:
                chunk=stream.read(min(32768,remaining))
                if not chunk:raise PackError('truncated_archive_entry')
                f.write(chunk);remaining-=len(chunk)
            f.flush();os.fsync(f.fileno())
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                mode=item.external_attr>>16
                if item.flag_bits&1 or (stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):raise PackError('linked_or_encrypted_archive_entry')
                with z.open(item) as f:save(item.filename,item.file_size,f,item.is_dir())
    else:
        with tarfile.open(archive,'r:*') as t:
            for item in t:
                if item.isdir():save(item.name,0,None,True)
                elif item.isfile():
                    with t.extractfile(item) as f:save(item.name,item.size,f)
                else:raise PackError('linked_or_special_archive_entry')

class PackStore:
    def __init__(self,home):
        self.root=physical(home,directory=True)
        if read(self.root/'store.json')!={'schema':'calf.pack.store.v1'}:raise PackError('pack_store_required')
        for name in ('versions','operations','locks','active','bindings'):physical(self.root/name,directory=True)

    @classmethod
    def create(cls,home):
        p=Path(home)
        if not p.is_absolute() or '..' in p.parts or p.exists() or p.is_symlink():raise PackError('new_store_folder_required')
        p.mkdir(parents=True,exist_ok=False);physical(p,directory=True)
        for name in ('versions','operations','locks','active','bindings'):(p/name).mkdir()
        atomic(p/'store.json',{'schema':'calf.pack.store.v1'},new=True)
        return cls(p)

    def version_root(self,id,version):
        if not isinstance(id,str) or not ID.fullmatch(id) or not isinstance(version,str) or not VERSION.fullmatch(version):raise PackError('invalid_pack_identity')
        relative(version)
        return self.root/'versions'/id/version

    def _op(self,kind,**details):
        path=self.root/'operations'/uuid.uuid4().hex;path.mkdir()
        atomic(path/'intent.json',{'kind':kind,**details},new=True);return path

    def _failure(self,op,error):
        if not (op/'result.json').exists():atomic(op/'result.json',{'status':'UNKNOWN','error':type(error).__name__+':'+str(error)[:500]},new=True)

    def stage(self,archive,expected_sha256,source):
        token(expected_sha256);archive=physical(archive)
        if not isinstance(source,str) or not 1<=len(source)<=512:raise PackError('source_provenance_required')
        if archive.stat().st_size>64*1024*1024:raise PackError('archive_size_limit')
        with mutex(self.root):
            op=self._op('stage',archiveSha256=expected_sha256,source=source)
            try:
                copy=op/'archive';size=0
                with archive.open('rb') as f,copy.open('xb') as out:
                    for chunk in iter(lambda:f.read(32768),b''):
                        size+=len(chunk)
                        if size>64*1024*1024:raise PackError('archive_size_limit')
                        out.write(chunk)
                    out.flush();os.fsync(out.fileno())
                if sha(copy)!=expected_sha256:raise PackError('archive_hash_mismatch')
                payload=op/'payload';extract(copy,payload);rows=inventory(payload);meta=package_metadata(payload)
                if meta['availability']=='reference':raise PackError('reference_pack_not_installable')
                target=self.version_root(meta['id'],meta['version'])
                info={'schema':'calf.pack.install.v1','id':meta['id'],'version':meta['version'],'archiveSha256':expected_sha256,
                      'manifestSha256':sha(payload/'pack.json'),'inventorySha256':sha(payload/'FILES.sha256'),'source':source,'operation':op.name}
                atomic(op/'prepared.json',info,new=True)
                if target.exists():
                    current=read(target/'install.json');inventory(target/'payload')
                    if current['archiveSha256']!=expected_sha256:raise PackError('released_version_identity_conflict')
                    atomic(op/'result.json',{'status':'ALREADY_STAGED','id':meta['id'],'version':meta['version']},new=True)
                    return current
                target.parent.mkdir(exist_ok=True);target.mkdir();os.replace(payload,target/'payload')
                atomic(target/'install.json',info,new=True);sync_directory(target)
                atomic(op/'result.json',{'status':'STAGED','id':meta['id'],'version':meta['version']},new=True)
                return info
            except BaseException as e:self._failure(op,e);raise

    def package(self,id,version):
        root=physical(self.version_root(id,version),directory=True);physical(root/'payload',directory=True)
        info=read(root/'install.json');meta=package_metadata(root/'payload')
        if (info['id'],info['version'])!=(id,version) or (meta['id'],meta['version'])!=(id,version):raise PackError('pack_identity_mismatch')
        inventory(root/'payload')
        if sha(root/'payload/pack.json')!=info['manifestSha256'] or sha(root/'payload/FILES.sha256')!=info['inventorySha256']:raise PackError('package_identity_changed')
        return root/'payload',meta,info

    def check(self,id,version,mode,environment):
        root,meta,info=self.package(id,version)
        return observe(root,meta,mode,environment)

    def qualify(self,id,version,mode,environment):
        with mutex(self.root):
            root,meta,info=self.package(id,version)
            compatibility=observe(root,meta,mode,environment)
            if compatibility['status']!='COMPATIBLE':raise PackError('compatibility_not_established:'+','.join(compatibility['reasons']))
            op=self._op('qualify',id=id,version=version,mode=mode)
            try:
                # Keep native snapshots below a conservative Windows path budget;
                # never change the machine's long-path policy to make a test pass.
                qa_root=self.root/'q';qa_root.mkdir(exist_ok=True);physical(qa_root,directory=True)
                qa=qa_root/op.name[:12]
                if os.name=='nt' and len(str(qa).encode('utf-16le'))//2>96:raise PackError('shorter_windows_pack_store_required')
                lock={'schema':'calf.pack.lock.v1','id':id,'version':version,'mode':mode,'packRoot':str(root),'install':info,
                      'manifestDigest':digest(meta),'files':inventory(root),'compatibility':compatibility,'qualification':op.name}
                if id=='calf.repository.navigator':
                    from .navigator import CHECKS
                    argv=[environment['python'],'-I','-S','-B','-X','utf8','-c',
                        'import sys,runpy;sys.path.insert(0,sys.argv.pop(1));sys.argv=sys.argv[1:];runpy.run_module("calf_extensions.repository.navigator_verify",run_name="__main__")',
                        str(root),'calf-navigator-verify','--git',environment['git'],'--output',str(qa)]
                    expected=CHECKS
                    if read(root/'qualification.json')['requiredChecks']!=CHECKS:raise PackError('navigator_check_contract')
                elif id=='calf.repository.local-git':
                    argv=[environment['python'],'-I','-S','-B','-X','utf8','-c',
                        'import sys,runpy;sys.path.insert(0,sys.argv.pop(1));sys.argv=sys.argv[1:];runpy.run_module("calf_extensions.repository.pack_verify",run_name="__main__")',
                        str(root),'calf-repository-verify','--git',environment['git'],'--output',str(qa)]
                    expected=read(root/'qualification.json')['requiredChecks']
                else:
                    argv=[environment['python'],'-I','-S','-B','-X','utf8','-c',
                        'import sys,runpy;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];sys.argv=sys.argv[1:];runpy.run_module("calf_extensions.media_ffmpeg.verify",run_name="__main__")',
                        str(root),environment['sdk'],'calf-media-verify','--calf',environment['calf'],
                        '--ffmpeg',environment['ffmpeg'],'--ffprobe',environment['ffprobe'],'--output',str(qa)]
                    expected=read(root/'VERIFICATION.json')['acceptanceChecks'][:-1]
                output=run(argv,timeout=180,limit=4*1024*1024,cwd=op)
                # Exit 0 is insufficient: read the actual bounded domain report.
                report=read(qa/'report.json')
                if report.get('status')!='PASS' or [x['check'] for x in report.get('checks',[])]!=expected:raise PackError('installation_checks_incomplete')
                if id=='calf.repository.local-git' and (expected!=['git-contracts','navigation-contracts','limits-contracts'] or any(not r.get('passed') or not r.get('tests') or r.get('skipped') for r in report['checks'])):raise PackError('repository_checks_incomplete')
                if id=='calf.repository.navigator' and any(not r.get('passed') or not r.get('tests') or r.get('skipped') for r in report['checks']):raise PackError('navigator_checks_incomplete')
                recheck_lock(lock);self.package(id,version)
                lock_id=digest(lock);atomic(self.root/'locks'/(lock_id+'.json'),lock,new=True)
                receipt={'status':'QUALIFIED','lock':lock_id,'reportSha256':sha(qa/'report.json'),'reportPath':str(qa/'report.json'),
                         'platform':compatibility['platform'],'checks':len(report['checks']),'logSha256':digest(output.decode('utf8','replace'))}
                atomic(op/'result.json',receipt,new=True)
                return {'lock':lock_id,'qualification':op.name,'status':'QUALIFIED','checks':receipt['checks']}
            except BaseException as e:self._failure(op,e);raise

    def load_lock(self,lock_id):
        token(lock_id);lock=read(self.root/'locks'/(lock_id+'.json'),1048576)
        if digest(lock)!=lock_id:raise PackError('lock_identity_changed')
        payload,meta,info=self.package(lock['id'],lock['version'])
        if str(payload)!=lock['packRoot'] or lock['install']!=info or inventory(payload)!=lock['files'] or digest(meta)!=lock['manifestDigest']:raise PackError('lock_payload_mismatch')
        recheck_lock(lock)
        if not re.fullmatch('[0-9a-f]{32}',lock['qualification']):raise PackError('qualification_identity')
        op=self.root/'operations'/lock['qualification'];receipt=read(op/'result.json')
        report=Path(receipt['reportPath']) if 'reportPath' in receipt else op/'qa/report.json'
        if report not in (self.root/'q'/op.name[:12]/'report.json',op/'qa/report.json'):raise PackError('qualification_report_path')
        if receipt.get('status')!='QUALIFIED' or receipt.get('lock')!=lock_id or receipt['reportSha256']!=sha(report):raise PackError('qualification_not_current')
        return lock

    def active(self,id):
        self.version_root(id,'0');p=self.root/'active'/(id+'.json')
        if not p.exists():return {'value':None,'digest':'none'}
        value=read(p)
        if value.get('id')!=id:raise PackError('active_identity_mismatch')
        return {'value':value,'digest':digest(value)}

    def activate(self,lock_id,expected_active,*,experimental=False):
        with mutex(self.root):
            lock=self.load_lock(lock_id);current=self.active(lock['id'])
            if current['digest']!=expected_active:raise PackError('active_version_changed')
            payload,meta,info=self.package(lock['id'],lock['version'])
            if (meta['availability']=='candidate' or meta['channel']!='stable') and not experimental:raise PackError('explicit_experimental_selection_required')
            value={'schema':'calf.pack.active.v1','id':lock['id'],'version':lock['version'],'mode':lock['mode'],'lock':lock_id}
            op=self._op('activate',before=current,after=value)
            try:
                atomic(self.root/'active'/(lock['id']+'.json'),value)
                atomic(op/'result.json',{'status':'ACTIVE','activeDigest':digest(value)},new=True)
                return self.active(lock['id'])
            except BaseException as e:self._failure(op,e);raise

    def recover(self,*,acknowledge=None,cursor=None):
        """Reconcile only manager transactions. Never execute or retry native work."""
        if acknowledge and cursor:raise PackError('choose_acknowledgement_or_listing')
        def inspect(op):
            intent=read(op/'intent.json');result=read(op/'result.json') if (op/'result.json').exists() else None
            if result and result.get('status')!='UNKNOWN':return None
            state='UNKNOWN'
            if intent['kind']=='activate':
                current=self.active(intent['after']['id'])
                if current['value']==intent['after']:
                    self.load_lock(intent['after']['lock']);state='COMMITTED_UNACKNOWLEDGED'
                elif current==intent['before']:state='NOT_APPLIED'
                else:state='SUPERSEDED_OR_UNKNOWN'
            elif intent['kind']=='stage' and (op/'prepared.json').exists():
                saved=read(op/'prepared.json')
                try:self.package(saved['id'],saved['version']);state='STAGED_UNACKNOWLEDGED'
                except (OSError,PackError):
                    target=self.version_root(saved['id'],saved['version'])
                    candidate=target/'payload' if (target/'payload').exists() else op/'payload'
                    try:
                        inventory(candidate)
                        if (sha(op/'archive')==saved['archiveSha256'] and sha(candidate/'pack.json')==saved['manifestSha256']
                            and sha(candidate/'FILES.sha256')==saved['inventorySha256'] and not (target/'install.json').exists()):state='RESUMABLE_STAGE'
                    except (OSError,PackError):pass
            return {'operation':op.name,'kind':intent['kind'],'status':state}
        with mutex(self.root):
            if acknowledge:
                if not re.fullmatch('[0-9a-f]{32}',acknowledge):raise PackError('operation_identity')
                op=self.root/'operations'/acknowledge;row=inspect(op)
                if row is None or row['status'] not in ('COMMITTED_UNACKNOWLEDGED','NOT_APPLIED','STAGED_UNACKNOWLEDGED','RESUMABLE_STAGE'):raise PackError('recovery_not_confirmed')
                if row['status']=='RESUMABLE_STAGE':
                    saved=read(op/'prepared.json');target=self.version_root(saved['id'],saved['version'])
                    target.parent.mkdir(exist_ok=True);target.mkdir(exist_ok=True)
                    if not (target/'payload').exists():os.replace(op/'payload',target/'payload')
                    atomic(target/'install.json',saved,new=True);self.package(saved['id'],saved['version'])
                    row['status']='STAGED_UNACKNOWLEDGED'
                atomic(op/'reconciliation.json',row,new=True);return row
            folder=self.root/'operations';generation=folder.stat().st_mtime_ns;after=None
            if cursor:
                import json
                if len(cursor)>256:raise PackError('invalid_recovery_cursor')
                position=json.loads(cursor);after=position['after']
                if position['generation']!=generation:raise PackError('recovery_listing_changed_restart')
            rows=[];scanned=0;found=after is None;last=None;more=False
            for op in folder.iterdir():
                if not found:
                    if op.name==after:found=True
                    continue
                if scanned>=128:more=True;break
                scanned+=1;last=op.name
                if (op/'reconciliation.json').exists():continue
                row=inspect(physical(op,directory=True))
                if row:rows.append(row)
            if not found:raise PackError('recovery_cursor_not_found')
            import json
            next_cursor=json.dumps({'after':last,'generation':generation},separators=(',',':')) if more else None
            return {'status':'UNKNOWN' if any(r['status'] in ('UNKNOWN','SUPERSEDED_OR_UNKNOWN') for r in rows) else 'PARTIAL' if more else 'RECONCILED',
                    'pending':rows,'limit':128,'scanned':scanned,'nextCursor':next_cursor,'pageOnly':cursor is not None}

    def bind(self,id,*,records,project):
        """New work freezes the active lock. Later execution never consults active."""
        with mutex(self.root):
            current=self.active(id)['value']
            if current is None:raise PackError('no_active_pack')
            lock=self.load_lock(current['lock']);folder=self.root/'bindings'/uuid.uuid4().hex;folder.mkdir()
            # Records/project are explicit external user roots, not pack files.
            records=Path(records);project=Path(project)
            for path in (records,project):
                physical(path,directory=True)
                if path.is_relative_to(self.root) or self.root.is_relative_to(path):raise PackError('work_data_outside_pack_store_required')
            if os.name=='nt' and len(str(records).encode('utf-16le'))//2>96:raise PackError('shorter_windows_records_path_required')
            worker=folder/'worker.py';worker.write_bytes(Path(__file__).with_name('ffmpeg_worker.py').read_bytes())
            value={'schema':'calf.pack.binding.v1','lock':current['lock'],'lockFile':str(self.root/'locks'/(current['lock']+'.json')),
                   'store':str(self.root),'records':str(records),'project':str(project),'workerSha256':sha(worker)}
            atomic(folder/'binding.json',value,new=True);return folder/'binding.json'
