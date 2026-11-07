"""Additive navigator mode and fixed binding/environment boundaries."""
import json,os
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from ..compatibility import observe
from ..io import PackError,read
from ..navigator import arguments,source_root

class NavigatorContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.meta=read(Path(__file__).parents[3]/'specs/pack-v1/examples/navigator.json');self.meta['modes'][0]['status']='implemented';self.env={}
        for name in ['python','git']:
            p=self.root/name;p.write_bytes(b'fixture');self.env[name]=str(p)
    def test_compatible_mode_has_no_core_sdk_and_manual_network_policy(self):
        def probe(argv,**kwargs):return b'{"version":"3.12.0","utf8":"utf-8"}' if '-c' in argv else b'git version 2.47.0\n'
        with patch('calf_extensions.packs.repository.run',probe):r=observe(self.root,self.meta,'navigate',self.env)
        self.assertEqual(r['status'],'COMPATIBLE');self.assertEqual(r['coreStatus'],'NOT_REQUIRED');self.assertFalse(r['networkPolicy']['automaticDiscovery'])
    def test_mode_cannot_broaden_network_or_native_authority(self):
        for field,value in [('network','none'),('supervised',True),('remoteDestinations',['https://evil.invalid'])]:
            m=json.loads(json.dumps(self.meta));m['modes'][0][field]=value
            with patch('calf_extensions.packs.repository.run',side_effect=AssertionError('unexpected executable')):r=observe(self.root,m,'navigate',self.env)
            self.assertEqual(r['status'],'UNKNOWN')
    def test_forwarded_arguments_cannot_override_pinned_paths_or_contain_secret_urls(self):
        for args in [['open','--repo=x'],['open','--data','x'],['scan','--git','x'],['open','--project-map=x'],['sources','add','--provider','github','--url','https://token@github.com/o/r'],['sources','add','--url=https://github.com/o/r?token=secret'],['open','--token','secret']]:
            with self.subTest(args=args),self.assertRaises(PackError):arguments(args)
        self.assertEqual(arguments(['--','open','--sources','--no-browser']),['open','--sources','--no-browser'])

class ChildEnvironment(unittest.TestCase):
    def test_windows_systemroot_is_retained_but_unselected_credentials_are_not(self):
        import os
        from unittest.mock import patch
        from calf_extensions.packs.navigator import child_environment
        for key in ['SystemRoot','SYSTEMROOT']:
            with patch.dict(os.environ,{key:'windows-root','TEMP':'owned-temp','SECRET_TOKEN':'must-not-cross'},clear=True):
                value=child_environment('/qualified/git')
                self.assertEqual(value[key],'windows-root');self.assertEqual(value['TEMP'],'owned-temp')
                self.assertNotIn('SECRET_TOKEN',value)

    def test_operational_credential_names_are_refused_case_insensitively(self):
        import os
        from unittest.mock import patch
        from calf_extensions.packs.navigator import launch
        from calf_extensions.packs.io import PackError
        for name in ['systemroot','Path','pythonpath','git_config','ssl_cert_file']:
            with patch('calf_extensions.packs.navigator.load',return_value=(None,None,None,None)), patch.dict(os.environ,{name:'example-value'}):
                with self.assertRaisesRegex(PackError,'operational_variable'):
                    launch(None,['open'],[name])
