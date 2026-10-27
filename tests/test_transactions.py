"""Transactional tests using a simulated Windows registry and power provider."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import modeshift as app

class MockBackend(app.Backend):
    def __init__(self):
        self.data={'history':[],'profiles':{},'automation':{}}
        self.registry={}
        self.power=app.POWER_SCHEMES['Balanced']
        self.persisted=[]
        self.fail_key=None
        self.fail_power=False
    def save(self):self.persisted.append(copy.deepcopy(self.data))
    def current_power(self):return self.power
    def set_power(self,guid):
        if self.fail_power:raise OSError('Simulated powercfg failure')
        self.power=guid
    def get_value(self,key):return copy.deepcopy(self.registry.get(key,{'exists':False,'data':None,'type':None}))
    def enabled(self,key):
        return self.get_value(key)['exists'] and str(self.get_value(key)['data'])==str(app.TW[key].on)
    def set_value(self,key,value):
        if key==self.fail_key:raise PermissionError('Simulated Windows policy')
        self.registry[key]={'exists':True,'data':value,'type':4} if value is not None else {'exists':False,'data':None,'type':None}
    def restore_value(self,key,original):self.registry[key]=copy.deepcopy(original)

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.patcher=patch.object(app,'on_windows',return_value=True)
        self.logger=patch.object(app,'log',return_value=None)
        self.patcher.start();self.logger.start()
        self.addCleanup(self.patcher.stop);self.addCleanup(self.logger.stop)
        self.engine=MockBackend()

    def test_journal_is_saved_before_first_registry_write(self):
        original=self.engine.set_value
        def spy(key,value):
            self.assertTrue(self.engine.persisted)
            self.assertEqual(self.engine.persisted[-1]['history'][-1]['status'],'pending')
            self.assertIn(key,self.engine.persisted[-1]['history'][-1]['before'])
            original(key,value)
        self.engine.set_value=spy
        result=self.engine.apply({'file_ext':True})
        self.assertEqual(result['count'],1)
        self.assertEqual(self.engine.data['history'][-1]['status'],'complete')

    def test_reversible_and_undo_can_be_redone(self):
        old=self.engine.get_value('file_ext')
        self.engine.apply({'file_ext':True})
        self.assertTrue(self.engine.enabled('file_ext'))
        self.engine.rollback()
        self.assertEqual(self.engine.get_value('file_ext'),old)
        self.engine.rollback()
        self.assertTrue(self.engine.enabled('file_ext'))

    def test_refuse_to_overwrite_manual_change(self):
        self.engine.apply({'file_ext':True})
        self.engine.registry['file_ext']={'exists':True,'data':123,'type':4}
        with self.assertRaises(app.SnapshotConflict):self.engine.rollback()
        self.assertEqual(self.engine.registry['file_ext']['data'],123)
        self.engine.rollback(force=True)
        self.assertFalse(self.engine.get_value('file_ext')['exists'])

    def test_partial_write_is_recorded_and_requires_force(self):
        self.engine.fail_key='hidden_files'
        response=self.engine.apply({'file_ext':True,'hidden_files':True})
        self.assertEqual(response['count'],1)
        self.assertTrue(response['failures'])
        self.assertEqual(self.engine.data['history'][-1]['status'],'partial')
        with self.assertRaises(app.SnapshotConflict):self.engine.rollback()
        self.engine.rollback(force=True)
        self.assertFalse(self.engine.enabled('file_ext'))

    def test_power_only_change_and_undo(self):
        high=app.POWER_SCHEMES['High performance']
        base=self.engine.power
        self.engine.apply({},high,'Auto power')
        self.assertEqual(self.engine.power,high)
        self.engine.rollback()
        self.assertEqual(self.engine.power,base)

    def test_power_conflict_preserves_external_choice(self):
        self.engine.apply({},app.POWER_SCHEMES['High performance'])
        self.engine.power=app.POWER_SCHEMES['Power saver']
        with self.assertRaises(app.SnapshotConflict):self.engine.rollback()
        self.assertEqual(self.engine.power,app.POWER_SCHEMES['Power saver'])

    def test_recommended_profile_priority_and_no_python_false_positive(self):
        a=app.detect_workloads(['python.exe'])
        self.assertNotIn('AI / Local models',a)
        self.assertEqual(app.recommend_profile(['Gaming','Roblox Studio']),'Roblox Studio / Dev')
        self.assertIsNone(app.recommend_profile([]))
        self.assertIsNone(app.recommend_profile(['Gaming'],{'Gaming':'Disabled'}))

    def test_legacy_snapshot_requires_confirmation(self):
        self.engine.apply({'file_ext':True})
        snap=self.engine.data['history'][-1]
        del snap['after_values']
        with self.assertRaises(app.SnapshotConflict):self.engine.rollback()
        self.engine.rollback(force=True)

if __name__=='__main__':unittest.main()
