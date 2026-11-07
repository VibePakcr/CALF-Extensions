import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from calf_extensions.packs.compatibility import observe
from calf_extensions.packs.io import PackError,read

SOURCE=Path(__file__).resolve().parents[3]

class RepositoryCompatibility(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.meta=read(SOURCE/'specs/pack-v1/examples/repository.json');self.meta['modes'][0]['status']='implemented'
        self.env={}
        for key in ('python','git'):
            p=self.root/key;p.write_bytes(b'not executed');self.env[key]=str(p)

    def probe(self,argv,**kwargs):
        return b'{"version":"3.12.0","utf8":"utf-8"}' if '-c' in argv else b'git version 2.50.0\n'

    def test_reference_and_unimplemented_modes_do_not_probe_dependencies(self):
        self.meta['modes'][0]['status']='planned'
        with patch('calf_extensions.packs.repository.run',side_effect=AssertionError('dependency executed')):
            result=observe(self.root,self.meta,'inspect',{})
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['dependencies'],[])

    def test_standalone_dependencies_and_no_core(self):
        with patch('calf_extensions.packs.repository.run',self.probe):result=observe(self.root,self.meta,'inspect',self.env)
        self.assertEqual(result['status'],'COMPATIBLE');self.assertEqual(result['coreStatus'],'NOT_REQUIRED')
        self.assertEqual({r['id'] for r in result['dependencies']},{'python','git'});self.assertTrue(result['qualificationRequired'])

    def test_declared_metadata_cannot_weaken_real_driver_floor(self):
        self.meta['dependencies'][1]['versionRange']['minInclusive']='1.0.0'
        def old(argv,**kwargs):return self.probe(argv,**kwargs) if '-c' in argv else b'git version 2.42.0\n'
        with patch('calf_extensions.packs.repository.run',old):result=observe(self.root,self.meta,'inspect',self.env)
        self.assertEqual(result['status'],'INCOMPATIBLE')
        self.meta['modes'][0]['dependencies']=[]
        with patch('calf_extensions.packs.repository.run',side_effect=AssertionError('dependency executed')):
            result=observe(self.root,self.meta,'inspect',self.env)
        self.assertEqual(result['status'],'UNKNOWN')

    def test_unknown_capabilities_and_extra_dependencies_are_not_assumed(self):
        self.meta['dependencies'][1]['requiredFeatures'].append('execute-repository-hooks')
        with patch('calf_extensions.packs.repository.run',self.probe):result=observe(self.root,self.meta,'inspect',self.env)
        self.assertEqual(result['status'],'UNKNOWN')
        with self.assertRaisesRegex(PackError,'explicit_repository_environment'):
            observe(self.root,self.meta,'inspect',dict(self.env,sdk='unwanted'))

if __name__=='__main__':unittest.main()
