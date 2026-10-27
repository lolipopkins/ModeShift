"""Measurement files are portable CSV and round-trip locally."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import modeshift as app

class MeasurementTests(unittest.TestCase):
    def test_csv_roundtrip(self):
        with TemporaryDirectory() as t, patch.object(app,'SESSION_DIR',Path(t)):
            rows=[
                {'time':1761500000.0,'cpu_percent':31.25,'ram_percent':81.0,'gpu_percent':94.0,'available_ram_gib':3.2,'workloads':'Blender / Rendering'},
                {'time':1761500004.0,'cpu_percent':41.5,'ram_percent':83.4,'gpu_percent':97.1,'available_ram_gib':2.7,'workloads':'Roblox Studio'},
            ]
            app.App.write_measurement(None,Path(t)/'measurement_20261026_120000.csv',rows)
            reloaded=app.App.load_measurements(None)
            self.assertEqual(reloaded, [rows])
            self.assertEqual(app.App.summarize_session(None,reloaded[0])['samples'],2)

if __name__=='__main__':unittest.main()
