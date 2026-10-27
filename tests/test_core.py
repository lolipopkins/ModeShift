"""Tests that do not require Windows, admin, or a display."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import modeshift as app

class CoreTests(unittest.TestCase):
    def test_unique_tweaks(self):
        self.assertEqual(len(app.TWEAKS),len(app.TW))
        self.assertGreaterEqual(len(app.TWEAKS),50)
    def test_valid_preset_keys(self):
        for name,config in app.PRESETS.items():
            self.assertIn(config['power'],app.POWER_SCHEMES)
            for key in config['tweaks']:
                self.assertIn(key,app.TW, name)
    def test_detect_multiple_workloads(self):
        self.assertEqual(app.detect_workloads(['BLENDER.exe','RobloxStudioBeta.exe']),['Blender / Rendering','Roblox Studio'])
    def test_pressure_recommendations(self):
        info={'ram_percent':93,'ram_available_gib':1.0,
              'gpus':[{'utilization':98,'vram_used_mib':7900,'vram_total_mib':8192}],
              'workloads':['Blender / Rendering','Roblox Studio']}
        recommendations=app.recommendations(info)
        self.assertGreaterEqual(len(recommendations),4)
    def test_no_pressure_recommendations(self):
        info={'ram_percent':30,'ram_available_gib':12,'gpus':None,'workloads':[]}
        self.assertEqual(len(app.recommendations(info)),1)

if __name__=='__main__':unittest.main()
