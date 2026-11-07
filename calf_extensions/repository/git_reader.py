"""Fixed Git read operations. Never run status, worktree diff or attribute filters."""
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from .model import MIN_GIT, RepositoryError, digest, oid, path_record

# None of these operations converts worktree contents through clean/process filters.
READ_OPERATIONS = ('--version', 'rev-parse', 'symbolic-ref', 'config', 'for-each-ref',
                   'ls-files', 'ls-tree', 'cat-file', 'log', 'diff-tree')
FLAGS = ['--no-pager', '--literal-pathspecs', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
         '-c', 'core.hooksPath='+os.devnull, '-c', 'color.ui=false', '-c', 'gc.auto=0',
         '-c', 'maintenance.auto=false', '-c', 'submodule.recurse=false', '-c', 'protocol.allow=never',
         '-c', 'credential.helper=']

class GitReader:
    def __init__(self, root, executable=None, timeout=30, output_limit=16*1024*1024):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise RepositoryError('INVALID_REPOSITORY', 'Repository root must be a directory')
        selected = str(executable) if executable else shutil.which('git')
        if not selected:
            raise RepositoryError('GIT_MISSING', 'Install Git before opening a repository', 4)
        self.executable = Path(selected).expanduser().resolve(strict=True)
        self.timeout, self.output_limit = timeout, output_limit
        self.cancel_event=threading.Event()
        self.env = {k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0',
                        GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1', GIT_ATTR_NOSYSTEM='1', LC_ALL='C')
        raw = self._read(['--version']).decode('ascii', errors='strict')
        match = re.search(r'git version (\d+)\.(\d+)(?:\.(\d+))?', raw)
        if not match or tuple(map(int, match.group(1,2))) < MIN_GIT:
            raise RepositoryError('GIT_UNSUPPORTED', 'Git 2.43 or newer with the required capabilities is needed', 4)
        self.version = match.group(0)

    def _read(self, args, input_data=None, allowed=(0,)):
        if args[0] not in READ_OPERATIONS or args[0]=='config' and args[1:3]!=['--null','--get-regexp']:
            raise RepositoryError('READ_OPERATION_REFUSED', 'Operation is not a fixed Git read')
        if self.cancel_event.is_set():raise RepositoryError('CANCELLED','Read cancelled',130)
        argv = [str(self.executable), *FLAGS, *args]
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as diagnostic:
            process = subprocess.Popen(argv, cwd=self.root, env=self.env, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                                       stdout=output, stderr=diagnostic, start_new_session=os.name!='nt',
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
            try:
                if input_data is not None:
                    process.stdin.write(input_data)
                    process.stdin.close()
                deadline = min(time.monotonic()+self.timeout,getattr(self,'total_deadline',float('inf')))
                while process.poll() is None:
                    if self.cancel_event.is_set():raise RepositoryError('CANCELLED','Read cancelled',130)
                    if time.monotonic()>deadline:
                        raise RepositoryError('GIT_TIMEOUT', 'Git read exceeded its time budget')
                    if os.fstat(output.fileno()).st_size>self.output_limit or os.fstat(diagnostic.fileno()).st_size>256*1024:
                        raise RepositoryError('GIT_OUTPUT_LIMIT', 'Git output exceeded its bound', 3)
                    time.sleep(.01)
                if os.fstat(output.fileno()).st_size>self.output_limit or os.fstat(diagnostic.fileno()).st_size>256*1024:
                    raise RepositoryError('GIT_OUTPUT_LIMIT', 'Git output exceeded its bound', 3)
                if process.returncode not in allowed:
                    raise RepositoryError('GIT_READ_FAILED', 'Git read failed: '+args[0])
                output.seek(0)
                return output.read(self.output_limit)
            finally:
                if process.poll() is None:
                    if os.name=='nt':
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4, check=False)
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=4)
                # Git is not allowed to spawn helpers. Close any owned remaining group.
                if os.name!='nt':
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass

    def discover(self):
        bare = self._read(['rev-parse','--is-bare-repository']).strip()==b'true'
        if bare:
            raise RepositoryError('BARE_UNSUPPORTED', 'Bare repositories are not supported in this preview', 4)
        root = Path(os.fsdecode(self._read(['rev-parse','--show-toplevel']).removesuffix(b'\n'))).resolve()
        private = Path(os.fsdecode(self._read(['rev-parse','--absolute-git-dir']).removesuffix(b'\n'))).resolve()
        common_raw = os.fsdecode(self._read(['rev-parse','--git-common-dir']).removesuffix(b'\n'))
        common = (self.root/common_raw).resolve()
        self.root = root
        partial = self._read(['config','--null','--get-regexp',r'^(extensions\.partialclone|remote\..*\.promisor)$'], allowed=(0,1))
        partial_values=[part.split(b'\n',1) for part in partial.split(b'\0') if part]
        is_partial=any(key.lower()==b'extensions.partialclone' or value.strip().lower() not in (b'false',b'no',b'off',b'0') for key,value in partial_values)
        if is_partial or any((common/'objects/pack').glob('*.promisor')):
            raise RepositoryError('PARTIAL_CLONE_UNSUPPORTED', 'Promisor/partial clones are not read or fetched', 4)
        fmt = self._read(['rev-parse','--show-object-format']).strip().decode('ascii')
        if fmt not in ('sha1','sha256'):
            raise RepositoryError('OBJECT_FORMAT_UNSUPPORTED', 'Unsupported Git object format',4)
        head = self._read(['rev-parse','--verify','--quiet','HEAD'], allowed=(0,1)).strip().decode('ascii') or None
        if head: oid(head, 40 if fmt=='sha1' else 64)
        branch = self._read(['symbolic-ref','--quiet','--short','HEAD'], allowed=(0,1)).rstrip(b'\n')
        self.info = {'root':str(root), 'git_dir':str(private), 'common_dir':str(common), 'object_format':fmt,
                     'git_version':self.version, 'head':head, 'branch':os.fsdecode(branch) if branch else None,
                     'state':'unborn' if head is None else 'branch' if branch else 'detached',
                     'shallow':self._read(['rev-parse','--is-shallow-repository']).strip()==b'true',
                     'linked_worktree':private!=common, 'status_basis':'RAW_BYTES',
                     'configuration_policy':'system/global config ignored; no trust settings changed'}
        return self.info

    def stages(self):
        raw = self._read(['ls-files','--stage','-z'])
        entries=[]
        for part in raw.split(b'\0'):
            if not part: continue
            header,path = part.split(b'\t',1)
            mode,blob,stage = header.decode('ascii').split(' ')
            entries.append(dict(path_record(path), mode=mode, oid=oid(blob), stage=int(stage)))
        return entries

    def tree(self, commit):
        raw = self._read(['ls-tree','-r','-z','--full-tree',oid(commit)])
        entries=[]
        for part in raw.split(b'\0'):
            if not part: continue
            header,path=part.split(b'\t',1);mode,kind,blob=header.decode('ascii').split(' ')
            entries.append(dict(path_record(path),mode=mode,kind=kind,oid=oid(blob)))
        return entries

    def refs(self):
        raw=self._read(['for-each-ref','--format=%(refname)%00%(objectname)%00','refs/heads','refs/tags'])
        result=[]
        for line in raw.splitlines():
            name,value,_=line.split(b'\0');result.append({'name':os.fsdecode(name),'oid':oid(value.decode('ascii'))})
        return result

    def blob(self, value):
        value=oid(value);size=int(self._read(['cat-file','-s',value]).strip())
        from .model import SOURCE_LIMIT
        if size>SOURCE_LIMIT:
            return None,size
        if self._read(['cat-file','-t',value]).strip()!=b'blob':
            raise RepositoryError('NOT_A_BLOB','Expected a file blob')
        raw=self._read(['cat-file','blob',value]);return raw,size

    def history(self, commit, offset=0, limit=200, path=None):
        args=['log','--topo-order','--format=%H%x00%P%x00%at%x00%an%x00%s%x00','--max-count='+str(limit+1),'--skip='+str(offset)]
        if path is not None:args+=['--follow','--find-renames=50%']
        args += [oid(commit),'--']
        if path is not None:args.append(os.fsdecode(path))
        # Format is length-bounded; parse exactly five NUL fields per record, not message lines.
        parts=self._read(args).split(b'\0');result=[]
        for i in range(0,len(parts)-1,5):
            block=parts[i:i+5]
            if len(block)!=5:raise RepositoryError('GIT_FORMAT','Incomplete commit record')
            value,parents,when,author,subject=block
            result.append({'id':oid(value.lstrip(b'\n').decode('ascii')), 'parents':[oid(x) for x in parents.decode('ascii').split()],
                           'timestamp':int(when),'author':author.decode('utf-8',errors='backslashreplace'),'subject':subject.decode('utf-8',errors='backslashreplace')})
        return result[:limit],len(result)>limit

    def changed(self, commit, parent=None):
        args=['diff-tree','--no-commit-id','--raw','-z','-r','--no-ext-diff','--no-textconv','--find-renames=50%']
        args += [oid(parent),oid(commit)] if parent else ['--root',oid(commit)]
        parts=self._read(args).split(b'\0');entries=[];i=0
        while i<len(parts) and parts[i]:
            header=parts[i].decode('ascii');i+=1
            old_mode,new_mode,old_oid,new_oid,status=header[1:].split(' ')
            original=path_record(parts[i]);i+=1;target=original
            if status.startswith(('R','C')):target=path_record(parts[i]);i+=1
            entries.append({'old':dict(original,mode=old_mode,oid=None if set(old_oid)=={'0'} else oid(old_oid)),
                            'new':dict(target,mode=new_mode,oid=None if set(new_oid)=={'0'} else oid(new_oid)), 'status':status})
        return entries
