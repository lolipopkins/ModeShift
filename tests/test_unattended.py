import sys, tempfile, json, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import modeshift as m

class GuardTests(unittest.TestCase):
    def setUp(self):self.cfg=m.GUARD_DEFAULTS.copy()
    def test_normal(self):
        self.assertEqual(m.assess_unattended({'ram_percent':50,'disk_percent':50,'gpus':[]},self.cfg),[])
    def test_thresholds(self):
        info={'ram_percent':95,'disk_percent':94,'gpus':[{'name':'GPU','vram_total_mib':1000,'vram_used_mib':950}]}
        result=m.assess_unattended(info,self.cfg)
        self.assertEqual([x[0] for x in result],['Critical','Warning','Warning'])
    def test_missing_gpu_and_ram(self):
        result=m.assess_unattended({'ram_percent':None,'disk_percent':None,'gpus':[{'name':'GPU','vram_total_mib':None,'vram_used_mib':None}]},self.cfg)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0][0],'Unknown')
    def test_event_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'guard.jsonl'
            m.write_guard_event(p,{'ram_percent':99,'workloads':['Blender / Rendering']}, [('Critical','RAM high')])
            x=json.loads(p.read_text().strip())
            self.assertEqual(x['alerts'][0][0],'Critical')
            self.assertEqual(x['workloads'],['Blender / Rendering'])
if __name__=='__main__':unittest.main()
