"""Public transport contracts against a supplied, unmodified CALF native binary."""
import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from calf_extensions.repository import context_lanes as cl
from calf_extensions.repository.model import RepositoryError


@unittest.skipUnless(os.environ.get('CALF_TEST_CORE'), 'Set CALF_TEST_CORE to a GCN-capable CALF binary')
class LaneTests(unittest.TestCase):
    def setUp(self):
        binary=Path(os.environ['CALF_TEST_CORE']).resolve(strict=True)
        self.native={'path':str(binary),'sha256':cl.hi.digest_file(binary)[0]}
        self.modules={'repository':{},'hosts':{}}
        self.plan={'schema':'calf.gcn.lanes.v1','cells':[
            {'id':'index','modules':['repository'],'dependsOn':[],'writes':['repo/index.py'],'checks':[],
             'contextRefs':[{'module':'repository','seq':1,'hash':'a'*64}]},
            {'id':'context','modules':['repository'],'dependsOn':['index'],'writes':['repo/context.py'],'checks':[]},
            {'id':'hosts','modules':['hosts'],'dependsOn':[],'writes':['hosts'],'checks':[]}],
            'lanes':[{'id':'repository','cells':['context']},{'id':'hosts','cells':['hosts']}]}

    def call(self):return cl.project(self.plan,self.modules,'repository',self.native)

    def refused(self,fn,code='CONTEXT_CORE_GCN_UNAVAILABLE'):
        with self.assertRaises(RepositoryError) as e:fn()
        self.assertEqual(e.exception.code,code)

    def test_native_orders_cells_and_returns_context_reference_identity(self):
        r=self.call()
        self.assertEqual([c['id'] for c in r['cells']],['index','context'])
        self.assertEqual(r['modules'],['repository']);self.assertEqual(r['controlEngine'],'CALF-native')
        self.assertEqual(r['controlCompute'],'CPU');self.assertEqual(r['executor'],'single')
        self.assertEqual(r['contextRefs'],self.plan['cells'][0]['contextRefs'])

    def test_native_refuses_dependency_cycles_and_missing_dependencies(self):
        self.plan['cells'][0]['dependsOn']=['context'];self.refused(self.call)
        self.plan['cells'][0]['dependsOn']=['missing'];self.refused(self.call)

    def test_native_refuses_overlapping_owners_and_absolute_write_paths(self):
        self.plan['cells'][0]['writes']=['repo'];self.refused(self.call)
        for path in ['C:/Windows/file','/tmp/file','../file']:
            self.plan['cells'][0]['writes']=[path];self.refused(self.call)

    def test_native_guard_refuses_unrelated_module(self):
        self.refused(lambda:cl.request(self.plan,self.modules,'guard',self.native,lane='repository',module='hosts'))

    def test_native_does_not_accept_caller_verdicts_or_commands(self):
        self.refused(lambda:cl.request(self.plan,self.modules,'project',self.native,lane='repository',nativeOutcome='SATISFIED'))
        self.plan['cells'][0]['command']=['echo','pass'];self.refused(self.call)

    def test_native_pin_checked_before_spawn(self):
        self.native['sha256']='0'*64
        with patch.object(cl.subprocess,'Popen',side_effect=AssertionError('must not execute changed core')):
            self.refused(self.call,'CONTEXT_NATIVE_CHANGED')

    def test_missing_native_has_no_python_fallback(self):
        with patch.object(cl.subprocess,'Popen',side_effect=AssertionError('must not guess a core')):
            self.refused(lambda:cl.project(self.plan,self.modules,'repository'),'CONTEXT_NATIVE_NOT_BOUND')

    def test_native_validates_without_mutating_plan_and_rejects_conflicting_reference(self):
        before=copy.deepcopy(self.plan)
        self.assertEqual(cl.validate(self.plan,self.modules,self.native)['state'],'VALID')
        self.call();self.assertEqual(self.plan,before)
        self.plan['cells'][1]['contextRefs']=[{'module':'repository','seq':1,'hash':'b'*64}]
        self.refused(self.call)


if __name__=='__main__':unittest.main()
