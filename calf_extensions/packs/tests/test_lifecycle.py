import copy
import io
import json
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
from calf_extensions.packs.io import PackError,sha,canonical,mutex,read
from calf_extensions.packs.metadata import manifest,in_range
from calf_extensions.packs.store import PackStore
from calf_extensions.packs.compatibility import observe

SOURCE=Path(__file__).resolve().parents[3]

class ContractTests(unittest.TestCase):
    source=SOURCE
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.store=PackStore.create(self.root/'store')
        self.meta=read(self.source/'specs/pack-v1/examples/ffmpeg.json');self.meta.update(availability='candidate',version='0.1.1-dev.9',channel='experimental')
        for entry in self.meta['entryPoints']:
            entry.update(status='planned');entry.pop('target');entry.pop('targetKind')
        self.meta['modes'][0]['status']='planned';self.counter=0
    def archive(self,meta=None,*,extra=None,mutate=None):
        self.counter+=1;p=self.root/('test-'+str(self.counter)+'.zip')
        files={'pack.json':canonical(meta or self.meta),'qualification.json':b'{}','VERIFICATION.json':b'{}',
               'docs/FFMPEG.md':b'English','docs/FFMPEG_KR.md':'한국어'.encode(),'do-not-import.py':b'raise RuntimeError("pack executed during metadata read")'}
        import hashlib
        files['FILES.sha256']=''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n' for k,v in sorted(files.items())).encode()
        if mutate:mutate(files)
        with zipfile.ZipFile(p,'x') as z:
            for k,v in files.items():z.writestr(k,v)
            if extra:extra(z)
        return p
    def stage(self,p):return self.store.stage(p,sha(p),'local-test-fixture')
    def test_strict_metadata_and_no_pack_import(self):
        p=self.root/'pack.json';p.write_bytes(canonical(self.meta));self.assertEqual(manifest(p)['id'],'calf.media.ffmpeg')
        p.write_text('{"schema":1,"schema":2}')
        with self.assertRaisesRegex(PackError,'duplicate_json'):manifest(p)
        for field,value in [('availability','invalid'),('version','1.0.0-01'),('permissions',{'shell':True})]:
            m=copy.deepcopy(self.meta);m[field]=value;p.write_bytes(canonical(m))
            with self.assertRaises(PackError):manifest(p)
    def test_dependency_references_and_numeric_bounds(self):
        p=self.root/'meta.json';m=copy.deepcopy(self.meta);m['modes'][0]['dependencies'].append('missing');p.write_bytes(canonical(m))
        with self.assertRaisesRegex(PackError,'dangling'):manifest(p)
        m=copy.deepcopy(self.meta);m['dependencies'][0]['versionRange']['maxExclusive']='3.0';p.write_bytes(canonical(m))
        with self.assertRaisesRegex(PackError,'inverted'):manifest(p)
        self.assertTrue(in_range('3.10',{'minInclusive':'3.10.0','maxExclusive':'4'}))
        with self.assertRaises(PackError):in_range('3.10rc1',{'minInclusive':'3','maxExclusive':'4'})
    def test_reference_pack_refused(self):
        m=copy.deepcopy(self.meta);m['availability']='reference'
        with self.assertRaisesRegex(PackError,'reference_pack'):self.stage(self.archive(m))
        self.assertIsNone(self.store.active(m['id'])['value'])
    def test_digest_mismatch_does_not_activate(self):
        p=self.archive()
        with self.assertRaisesRegex(PackError,'archive_hash'):self.store.stage(p,'0'*64,'local-test-fixture')
        self.assertIsNone(self.store.active(self.meta['id'])['value'])
    def test_inventory_extra_and_modified_files(self):
        for change in [lambda d:d.update({'extra.py':b'new'}),lambda d:d.update({'docs/FFMPEG.md':b'changed'})]:
            with self.assertRaisesRegex(PackError,'inventory_mismatch'):self.stage(self.archive(mutate=change))
    def test_traversal_reserved_names_and_case_collision(self):
        for name in ['../outside','/absolute','dir\\outside','CON.txt','a:stream','a.','d/../../outside']:
            with self.assertRaises(PackError):self.stage(self.archive(extra=lambda z:z.writestr(name,b'x')))
        with self.assertRaisesRegex(PackError,'colliding'):
            self.stage(self.archive(extra=lambda z:(z.writestr('Case/a',b'a'),z.writestr('case/b',b'b'))))
        self.assertFalse((self.root/'outside').exists())
    def test_links_and_duplicate_entries(self):
        def link(z):
            info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'../../elsewhere')
        with self.assertRaisesRegex(PackError,'linked'):self.stage(self.archive(extra=link))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            p=self.archive(extra=lambda z:z.writestr('pack.json',b'{}'))
        with self.assertRaisesRegex(PackError,'duplicate_archive'):self.stage(p)
    def test_advertised_expansion_limit_before_allocation(self):
        p=self.root/'oversized.tar';header=tarfile.TarInfo('large.bin');header.size=256*1024*1024+1;p.write_bytes(header.tobuf()+b'\0'*1024)
        with self.assertRaisesRegex(PackError,'archive_size_limit'):self.stage(p)
    def test_file_count_limit(self):
        p=self.root/'many.zip'
        with zipfile.ZipFile(p,'x') as z:
            for i in range(4097):z.writestr('f'+str(i),b'')
        with self.assertRaisesRegex(PackError,'archive_size_limit'):self.stage(p)
    def test_version_identity_and_idempotent_stage(self):
        p=self.archive();first=self.stage(p);self.assertEqual(self.stage(p),first)
        second=self.archive(mutate=lambda d:d.update({'do-not-import.py':b'changed'}))
        # Still rejected, even if a changed package claims the same version.
        with self.assertRaises(PackError):self.stage(second)
        self.assertEqual(self.store.package(first['id'],first['version'])[2],first)
    def test_missing_target_and_unknown_driver(self):
        m=read(self.source/'specs/pack-v1/examples/repository.json')
        report=observe(self.root,m,'inspect',{})
        self.assertEqual(report['status'],'UNKNOWN');self.assertEqual(report['coreStatus'],'NOT_REQUIRED')
        self.assertEqual(report['dependencies'],[])
    def test_mutex_releases_and_no_nested_mutation(self):
        p=self.archive()
        with mutex(self.store.root):
            with self.assertRaisesRegex(PackError,'store_busy'):self.stage(p)
        self.stage(p)
    def test_interrupted_install_reconciles_without_execution(self):
        p=self.archive();from calf_extensions.packs import store as module
        original=module.atomic
        def fail(path,*a,**kw):
            if Path(path).name=='install.json':raise OSError('injected-install-reply-loss')
            return original(path,*a,**kw)
        with patch.object(module,'atomic',fail):
            with self.assertRaises(OSError):self.stage(p)
        row=self.store.recover()['pending'][0];self.assertEqual(row['status'],'RESUMABLE_STAGE')
        self.store.recover(acknowledge=row['operation']);self.store.package(self.meta['id'],self.meta['version'])
        self.assertIsNone(self.store.active(self.meta['id'])['value'])
        self.assertEqual(self.store.recover()['pending'],[])
        self.assertEqual(read(self.store.root/'operations'/row['operation']/'result.json')['status'],'UNKNOWN')
    def test_recovery_pages_without_preloading_history(self):
        from calf_extensions.packs.io import atomic
        for _ in range(130):
            op=self.store._op('stage',archiveSha256='0'*64,source='fixture')
            atomic(op/'result.json',{'status':'STAGED'},new=True)
        first=self.store.recover();self.assertEqual(first['scanned'],128);self.assertEqual(first['status'],'PARTIAL')
        second=self.store.recover(cursor=first['nextCursor']);self.assertEqual(second['scanned'],2);self.assertTrue(second['pageOnly'])
        self.store._op('stage',archiveSha256='0'*64,source='fixture')
        with self.assertRaisesRegex(PackError,'listing_changed'):self.store.recover(cursor=first['nextCursor'])
    def test_locked_dependency_drift(self):
        from calf_extensions.packs.compatibility import recheck_lock,platform_id
        p=self.root/'tool.bin';p.write_bytes(b'original')
        lock={'schema':'calf.pack.lock.v1','compatibility':{'status':'COMPATIBLE','platform':platform_id(),'fingerprints':{str(p):sha(p)}}}
        recheck_lock(lock);p.write_bytes(b'changed')
        with self.assertRaisesRegex(PackError,'dependency_identity_changed'):recheck_lock(lock)
    def test_missing_and_known_unsupported_versions_are_distinct(self):
        from calf_extensions.packs import compatibility as module
        sdk=self.root/'sdk';(sdk/'calf_sdk').mkdir(parents=True)
        for name in ('client.py','adapter.py','work.py'):(sdk/'calf_sdk'/name).write_text('# unit fixture')
        init=sdk/'calf_sdk/__init__.py';init.write_text('__version__="0.2.0"')
        env={'sdk':str(sdk),'edition':'harness'}
        for name in ('python','calf','ffmpeg','ffprobe'):
            p=self.root/name;p.write_bytes(b'unit-fixture');env[name]=str(p)
        (self.root/'VERIFICATION.json').write_bytes(canonical({'platforms':{module.platform_id():{'cores':{'harness':{'sha256':sha(env['calf'])}},'FFmpeg':'8.1.2'}}}))
        def probe(argv,**kwargs):
            if '-c' in argv:return b'{"version":"3.12.0","utf8":"utf-8"}'
            if '--version' in argv:return b'{"version":"1.8.7"}'
            if '-version' in argv:return (Path(argv[0]).name+' version 8.1.2 unit fixture').encode()
            if '-encoders' in argv:return b' V....D libx264 video\n A..... aac audio\n'
            if '-filters' in argv:return b' .S blackdetect V->V\n .. silencedetect A->A\n'
            if '-protocols' in argv:return b'  file\n'
            return b' -print_format format\n'
        with patch.object(module,'run',probe):
            report=observe(self.root,self.meta,'scenes',env)
            # Use the implemented mode for probe tests, not the archive-only planned fixture.
            implemented=copy.deepcopy(self.meta);implemented['modes'][0]['status']='implemented'
            report=observe(self.root,implemented,'scenes',env)
            row=next(x for x in report['dependencies'] if x['id']=='calf-sdk')
            self.assertEqual(row['status'],'INCOMPATIBLE')
            env['ffmpeg']=str(self.root/'missing')
            report=observe(self.root,implemented,'scenes',env)
            row=next(x for x in report['dependencies'] if x['id']=='ffmpeg')
            self.assertEqual((row['status'],row['reason']),('INCOMPATIBLE','dependency_missing'))

if __name__=='__main__':unittest.main()
